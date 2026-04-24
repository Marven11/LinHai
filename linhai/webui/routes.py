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
    ConfigResponse,
    ProfileInfo,
    LlmInfo,
    LlmDetailInfo,
    LlmListResponse,
    SwitchLlmRequest,
    KillProcessRequest,
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


from pathlib import Path


@router.post("", response_model=AgentCreateResponse)
async def create_agent(request: AgentCreateRequest):
    from linhai.agent.create import AgentBuildArguments as _AgentBuildArguments

    if request.claw_folder:
        claw_folder_path = Path(request.claw_folder)
        if not claw_folder_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"CLAW目录不存在或不是目录: {request.claw_folder}",
            )
    else:
        claw_folder_path = None

    file_paths: list[Path] = []
    for f in request.file:
        p = Path(f)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"文件不存在: {f}")
        file_paths.append(p)

    checklist_path = None
    if request.checklist_path:
        checklist_path = Path(request.checklist_path)
        if not checklist_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"检查清单文件不存在或不是文件: {request.checklist_path}",
            )

    build_args: _AgentBuildArguments = {
        "rss": request.rss,
        "telegram": request.telegram,
        "disable_waiting_marker": request.disable_waiting_marker,
        "afk": request.afk,
        "claw_enabled": request.claw_enabled,
        "claw_folder": claw_folder_path,
        "message": request.message,
        "file": file_paths,
        "planning": request.planning,
        "llm_name": request.llm_name,
        "checklist_path": checklist_path,
        "profile_name": request.profile_name,
        "git_worktree": False,
    }

    manager = get_manager()
    session = await manager.create_agent(build_args)
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

        async with anyio.create_task_group() as tg:
            tg.start_soon(receive_segments)
            await parsed_answer.wait_parsing()
            tg.cancel_scope.cancel()

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

            session.sync_processes()
            session.sync_status_bar()
            session.sync_planning()
            session.sync_context()

            for event in events:
                await websocket.send_json(event)
            elapsed = time.perf_counter() - start_time
            if elapsed < 0.1:
                await asyncio.sleep(0.1 - elapsed)

        tg.cancel_scope.cancel()


@router.get("/{agent_id}/llms", response_model=LlmListResponse)
async def get_agent_llms(agent_id: str):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    llms_data = session.get_llms()
    llm_infos = []
    for item in llms_data:
        llm_infos.append(
            LlmDetailInfo(
                name=item["name"],
                model=item["model"],
                token_limit=item["token_limit"],
                support_image=item["support_image"],
                is_current=item["is_current"],
                is_default=item["is_default"],
                error_count=item["error_count"],
            )
        )
    return LlmListResponse(llms=llm_infos)


@router.post("/{agent_id}/switch_llm")
async def switch_agent_llm(agent_id: str, request: SwitchLlmRequest):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    available = session.get_llms()
    valid_names = [l["name"] for l in available]
    if request.llm_name not in valid_names:
        raise HTTPException(
            status_code=400,
            detail=f"LLM {request.llm_name} 不存在，可用: {', '.join(valid_names)}",
        )
    await session.switch_llm(request.llm_name)
    return {"message": f"已切换到LLM: {request.llm_name}"}


@router.post("/{agent_id}/processes/{pid}/kill")
async def kill_agent_process(agent_id: str, pid: str, request: KillProcessRequest):
    manager = get_manager()
    session = manager.get_agent(agent_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Agent不存在")
    success = await session.kill_process(pid, request.machine_id)
    if not success:
        raise HTTPException(status_code=404, detail="进程不存在或终止失败")
    return {"message": f"进程 {pid} 已终止"}


@config_router.get("/config", response_model=ConfigResponse)
async def get_config():
    manager = get_manager()
    info = manager.get_config_info()
    return ConfigResponse(
        profiles=[ProfileInfo(**p) for p in info["profiles"]],
        llms=[LlmInfo(**l) for l in info["llms"]],
    )
