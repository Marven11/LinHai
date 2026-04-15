import anyio
import asyncio
import json
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket

from .schemas import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentInfo,
    AgentListResponse,
    WsStateChangeEvent,
    ContextStatsResponse,
    TokenUsageInfo,
    PlanningFileResponse,
    ConfigResponse,
    ProfileInfo,
    LlmInfo,
)
from .agent_manager import AgentManager
from ..config import get_default_config_path

router = APIRouter(prefix="/api/agents", tags=["agents"])
config_router = APIRouter(prefix="/api", tags=["config"])

_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager(get_default_config_path())
    return _manager


@router.post("", response_model=AgentCreateResponse)
async def create_agent(request: AgentCreateRequest):
    manager = get_manager()
    session = await manager.create_agent(
        profile_name=request.profile_name,
        init_messages=request.init_messages,
    )
    return AgentCreateResponse(
        id=session.agent_id,
        state=session.get_state(),
    )


@router.get("", response_model=AgentListResponse)
async def list_agents():
    manager = get_manager()
    sessions = manager.list_agents()
    agents = [
        AgentInfo(
            id=session.agent_id,
            state=session.get_state(),
            current_llm=session.get_current_llm(),
            created_at=session.created_at.isoformat(),
        )
        for session in sessions
    ]
    return AgentListResponse(agents=agents)


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return AgentInfo(
        id=session.agent_id,
        state=session.get_state(),
        current_llm=session.get_current_llm(),
        created_at=session.created_at.isoformat(),
    )


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    manager = get_manager()
    success = await manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return {"message": "Agent已停止并销毁"}


@router.websocket("/{agent_id}/ws")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        await websocket.close(code=4040, reason="Agent不存在")
        return

    await websocket.accept()

    registry = session.registry

    if "ui_log" not in registry.queues:
        registry.register_queue("ui_log")

    if "parsed_agent_answer" not in registry.queues:
        registry.register_queue("parsed_agent_answer")

    prev_state: Optional[str] = None
    client_disconnected = anyio.Event()

    async def monitor_disconnect():
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                client_disconnected.set()
                return
            if msg["type"] == "websocket.receive":
                text = msg.get("text")
                if text is None:
                    continue
                data = json.loads(text)
                if data.get("type") == "user_message":
                    await session.send_message(data["content"])
                elif data.get("type") == "reset":
                    reset_event = await session.handle_reset()
                    await websocket.send_json(reset_event)

    async def handle_parsed_answer(parsed_answer):
        agent_idx = session.add_agent_message()

        async def receive_segments():
            while True:
                segment = await parsed_answer.segment_queue.get()
                session.add_segment_to_agent_message(agent_idx, segment)
                content = parsed_answer._answer.get_current_content()
                session.update_agent_message_content(agent_idx, content)

        receive_task = asyncio.create_task(receive_segments())
        await parsed_answer.wait_parsing()
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass

        content = parsed_answer._answer.get_current_content()
        session.update_agent_message_content(agent_idx, content)

    async with anyio.create_task_group() as tg:
        tg.start_soon(monitor_disconnect)

        while not client_disconnected.is_set():
            start_time = time.perf_counter()
            events: list = []

            tagged_events = await session.get_diff()
            for tagged_event in tagged_events:
                events.append(tagged_event)

            while not registry.is_empty("parsed_agent_answer"):
                parsed_answer = await registry.receive("parsed_agent_answer")
                tg.start_soon(handle_parsed_answer, parsed_answer)

            while not registry.is_empty("ui_log"):
                notice = await registry.receive("ui_log")
                session.add_notification(notice.level, notice.content)

            tagged_events_after = await session.get_diff()
            for tagged_event in tagged_events_after:
                events.append(tagged_event)

            current_state = session.get_state()
            if prev_state is not None and current_state != prev_state:
                events.append(
                    WsStateChangeEvent(
                        old_state=prev_state, new_state=current_state
                    ).model_dump()
                )
            prev_state = current_state

            for event in events:
                await websocket.send_json(event)
            elapsed = time.perf_counter() - start_time
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        tg.cancel_scope.cancel()


@router.get("/{agent_id}/context", response_model=ContextStatsResponse)
async def get_agent_context(agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    stats = session.get_context_stats()
    cumulative = None
    if stats["cumulative_token_usage"] is not None:
        cumulative = TokenUsageInfo(**stats["cumulative_token_usage"])
    return ContextStatsResponse(
        message_count=stats["message_count"],
        pinned_message_count=stats["pinned_message_count"],
        notification_count=stats["notification_count"],
        large_message_count=stats["large_message_count"],
        traffic_light=stats["traffic_light"],
        context_usage_ratio=stats["context_usage_ratio"],
        is_dirty=stats["is_dirty"],
        cumulative_token_usage=cumulative,
        generation_count=stats["generation_count"],
    )


@router.get("/{agent_id}/planning", response_model=PlanningFileResponse)
async def get_agent_planning(agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    files = session.get_planning_files()
    return PlanningFileResponse(**files)


@config_router.get("/config", response_model=ConfigResponse)
async def get_config():
    manager = get_manager()
    info = manager.get_config_info()
    return ConfigResponse(
        profiles=[ProfileInfo(**p) for p in info["profiles"]],
        llms=[LlmInfo(**l) for l in info["llms"]],
    )
