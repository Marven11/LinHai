from typing import Optional, Literal, TypedDict, Union
from pydantic import BaseModel, Field


class WebuiSegmentType(TypedDict):
    segment_type: Literal["reasoning", "normal", "toolcall"]
    content: str
    is_finished: bool


class WebuiUserMessage(TypedDict):
    type: Literal["user"]
    content: str


class WebuiNotificationMessage(TypedDict):
    type: Literal["notification"]
    level: str
    content: str


class WebuiAgentMessage(TypedDict):
    type: Literal["agent"]
    content: str
    segments: list[WebuiSegmentType]


WebuiMessage = Union[WebuiUserMessage, WebuiNotificationMessage, WebuiAgentMessage]


class WsStateChangeEvent(BaseModel):
    type: Literal["state_change"] = "state_change"
    old_state: str = Field(..., description="旧状态")
    new_state: str = Field(..., description="新状态")


class AgentCreateRequest(BaseModel):
    profile_name: Optional[str] = Field(default=None, description="Agent profile名称")
    llm_name: Optional[str] = Field(default=None, description="指定使用的LLM名称")
    planning: bool = Field(default=False, description="启用文档规划模式")
    afk: bool = Field(default=False, description="禁止Agent暂停")
    disable_waiting_marker: bool = Field(
        default=False, description="关闭出现#LINHAI_WAITING_USER才暂停的功能"
    )
    claw_enabled: bool = Field(default=False, description="启用CLAW模式")
    claw_folder: Optional[str] = Field(default=None, description="CLAW目录路径")
    checklist_path: Optional[str] = Field(default=None, description="检查清单文件路径")
    rss: list[str] = Field(default_factory=list, description="RSS feed URL列表")
    telegram: bool = Field(default=False, description="启用Telegram远程控制")
    message: list[str] = Field(default_factory=list, description="初始用户消息列表")
    file: list[str] = Field(default_factory=list, description="初始文件路径列表")


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


class TokenUsageInfo(BaseModel):
    input_tokens: int = Field(..., description="输入token数")
    output_tokens: int = Field(..., description="输出token数")
    total_tokens: int = Field(..., description="总token数")
    cached_input_tokens: int = Field(..., description="缓存命中的输入token数")
    cache_creation_input_tokens: int = Field(..., description="缓存创建的输入token数")
    message_count: int = Field(..., description="消息生成次数")
    cache_miss_count: int = Field(..., description="缓存未命中次数")


class ContextStatsResponse(BaseModel):
    message_count: int = Field(..., description="普通消息数量")
    pinned_message_count: int = Field(..., description="置顶消息数量")
    notification_count: int = Field(..., description="通知消息数量")
    large_message_count: int = Field(..., description="大消息数量")
    traffic_light: str = Field(..., description="红绿灯状态: 绿灯/黄灯/红灯")
    context_usage_ratio: Optional[float] = Field(
        default=None, description="上下文使用率"
    )
    is_dirty: bool = Field(..., description="token用量是否已失效")
    cumulative_token_usage: Optional[TokenUsageInfo] = Field(
        default=None, description="累计token用量"
    )
    generation_count: int = Field(..., description="生成次数")


class PlanningFileResponse(BaseModel):
    status: Optional[str] = Field(default=None, description="STATUS.md内容")
    todolist: Optional[str] = Field(default=None, description="TODOLIST.md内容")
    design: Optional[str] = Field(default=None, description="DESIGN.md内容")


class LlmInfo(BaseModel):
    name: str = Field(..., description="LLM名称")
    model: str = Field(..., description="模型名称")
    type: str = Field(..., description="LLM类型")


class ProfileInfo(BaseModel):
    name: str = Field(..., description="Profile名称")


class LlmDetailInfo(BaseModel):
    name: str = Field(..., description="LLM名称")
    model: str = Field(..., description="模型名称")
    token_limit: int = Field(..., description="token限制")
    support_image: bool = Field(..., description="是否支持图像")
    is_current: bool = Field(..., description="是否是当前使用的LLM")
    is_default: bool = Field(..., description="是否是默认LLM")
    error_count: int = Field(..., description="错误计数")


class LlmListResponse(BaseModel):
    llms: list[LlmDetailInfo] = Field(default_factory=list, description="LLM列表")


class SwitchLlmRequest(BaseModel):
    llm_name: str = Field(..., description="要切换到的LLM名称")


class ProcessInfo(BaseModel):
    pid: str = Field(..., description="进程ID")
    machine_id: str = Field(..., description="机器ID")
    argv: list[str] = Field(default_factory=list, description="进程参数列表")
    status: Literal["running", "exited", "error"] = Field(..., description="进程状态")
    returncode: Optional[int] = Field(default=None, description="退出码")


class WsProcessUpdateEvent(BaseModel):
    type: Literal["process_update"] = "process_update"
    events: list


class WsStatusBarUpdateEvent(BaseModel):
    type: Literal["status_bar_update"] = "status_bar_update"
    events: list


class KillProcessRequest(BaseModel):
    machine_id: str = Field(..., description="进程所在机器ID")


class ConfigResponse(BaseModel):
    profiles: list[ProfileInfo] = Field(
        default_factory=list, description="可用Profile列表"
    )
    llms: list[LlmInfo] = Field(default_factory=list, description="可用LLM列表")
