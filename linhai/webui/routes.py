"""WebUI路由定义。"""

from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import asyncio
import json

from .schemas import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentInfo,
    AgentListResponse,
    MessageRequest,
)
from .agent_manager import AgentManager, AgentSession

router = APIRouter(prefix="/api/agents", tags=["agents"])


_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    """获取全局AgentManager实例。"""
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager


@router.post("", response_model=AgentCreateResponse)
async def create_agent(request: AgentCreateRequest):
    """创建新的Agent实例。"""
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
    """列出所有Agent实例及其状态。"""
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
    """获取指定Agent的状态。"""
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
    """停止并销毁指定的Agent。"""
    manager = get_manager()
    success = await manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return {"message": "Agent已停止并销毁"}
