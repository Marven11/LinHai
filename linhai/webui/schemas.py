"""WebUI的Pydantic模型定义。"""

from typing import Optional
from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    """创建Agent的请求模型。"""

    profile_name: Optional[str] = Field(default=None, description="Agent profile名称")
    init_messages: list[str] = Field(
        default_factory=list, description="初始用户消息列表"
    )


class AgentInfo(BaseModel):
    """Agent信息模型。"""

    id: str = Field(..., description="Agent唯一标识")
    state: str = Field(..., description="Agent当前状态")
    current_llm: Optional[str] = Field(default=None, description="当前使用的LLM名称")
    created_at: str = Field(..., description="创建时间")


class AgentListResponse(BaseModel):
    """Agent列表响应模型。"""

    agents: list[AgentInfo] = Field(default_factory=list, description="Agent列表")


class AgentCreateResponse(BaseModel):
    """创建Agent的响应模型。"""

    id: str = Field(..., description="创建的Agent唯一标识")
    state: str = Field(..., description="Agent当前状态")
    message: str = Field(default="Agent创建成功", description="响应消息")


class MessageRequest(BaseModel):
    """发送消息的请求模型。"""

    content: str = Field(..., description="消息内容")
