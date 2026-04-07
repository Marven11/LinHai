"""WebUI的Pydantic模型定义。"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    profile_name: Optional[str] = Field(default=None, description="Agent profile名称")
    init_messages: list[str] = Field(
        default_factory=list, description="初始用户消息列表"
    )


class AgentInfo(BaseModel):
    id: str = Field(..., description="Agent唯一标识")
    state: str = Field(..., description="Agent当前状态")
    current_llm: Optional[str] = Field(default=None, description="当前使用的LLM名称")
    created_at: str = Field(..., description="创建时间")


class AgentListResponse(BaseModel):
    agents: list[AgentInfo] = Field(default_factory=list, description="Agent列表")


class AgentCreateResponse(BaseModel):
    id: str = Field(..., description="创建的Agent唯一标识")
    state: str = Field(..., description="Agent当前状态")
    message: str = Field(default="Agent创建成功", description="响应消息")


class MessageRequest(BaseModel):
    content: str = Field(..., description="消息内容")


class MessageItem(BaseModel):
    role: str = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")


class MessageListResponse(BaseModel):
    messages: list[MessageItem] = Field(default_factory=list, description="消息列表")


class WsSegmentEvent(BaseModel):
    type: Literal["segment"] = "segment"
    segment_type: str = Field(..., description="segment类型")
    content: str = Field(..., description="segment内容")
    is_finished: bool = Field(..., description="segment是否完成")


class WsUiLogEvent(BaseModel):
    type: Literal["ui_log"] = "ui_log"
    level: str = Field(..., description="日志级别")
    content: str = Field(..., description="日志内容")


class WsStateChangeEvent(BaseModel):
    type: Literal["state_change"] = "state_change"
    old_state: str = Field(..., description="旧状态")
    new_state: str = Field(..., description="新状态")
