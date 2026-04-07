"""WebUI路由定义。"""

import anyio
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket

from .schemas import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentInfo,
    AgentListResponse,
    MessageRequest,
    MessageListResponse,
    MessageItem,
    WsSegmentEvent,
    WsUiLogEvent,
    WsStateChangeEvent,
)
from .agent_manager import AgentManager, AgentSession

router = APIRouter(prefix="/api/agents", tags=["agents"])

_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager()
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


@router.post("/{agent_id}/messages")
async def send_message(agent_id: str, request: MessageRequest):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    await session.send_message(request.content)
    return {"message": "消息已发送"}


@router.get("/{agent_id}/messages", response_model=MessageListResponse)
async def get_messages(agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    messages = session.get_messages()
    return MessageListResponse(
        messages=[MessageItem(role=m["role"], content=m["content"]) for m in messages]
    )


@router.websocket("/{agent_id}/ws")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        await websocket.close(code=4040, reason="Agent不存在")
        return

    await websocket.accept()

    registry = session.registry
    agent = session.agent

    if "ui_log" not in registry.queues:
        registry.register_queue("ui_log")

    active_segments: list[dict] = []
    prev_state: Optional[str] = None
    client_disconnected = anyio.Event()

    async def monitor_disconnect():
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                client_disconnected.set()
                return

    async def on_segment(parsed_answer, segment):
        active_segments.append(segment)

    async def on_segment_finished(parsed_answer, segment):
        if segment in active_segments:
            active_segments.remove(segment)

    session.agent.lifecycle.after_segment.register(on_segment)
    session.agent.lifecycle.after_segment_finished.register(on_segment_finished)

    async with anyio.create_task_group() as tg:
        tg.start_soon(monitor_disconnect)

        while not client_disconnected.is_set():
            events: list[dict] = []

            for segment in list(active_segments):
                events.append(
                    WsSegmentEvent(
                        segment_type=segment["segment_type"],
                        content=segment["content"],
                        is_finished=segment["is_finished"],
                    ).model_dump()
                )

            while not registry.is_empty("ui_log"):
                notice = await registry.receive("ui_log")
                events.append(
                    WsUiLogEvent(
                        level=notice.level, content=notice.content
                    ).model_dump()
                )

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

            await asyncio.sleep(0.2)

        tg.cancel_scope.cancel()

    session.agent.lifecycle.after_segment._callbacks.remove(on_segment)
    session.agent.lifecycle.after_segment_finished._callbacks.remove(
        on_segment_finished
    )
