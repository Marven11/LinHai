"""
传给OpenAI的LLM Message定义等

我们完全弃用OpenAI的工具调用功能
"""

from __future__ import annotations
from typing import Union, Optional, Iterable, TypedDict, Literal
from typing_extensions import Required, TypeAlias, NotRequired

AgentState = Literal["waiting_user", "working"]


class ChatCompletionContentPartTextParam(TypedDict):
    """Parameters for text content part in chat completion."""

    text: Required[str]
    type: Required[Literal["text"]]
    cache_control: NotRequired[dict]


class ChatCompletionMessageToolCallParam(TypedDict):
    """Parameters for tool call in chat completion."""

    id: Required[str]
    function: Required[dict]
    type: Required[Literal["function"]]


class Audio(TypedDict):
    """Audio data type definition."""

    id: Required[str]


class FunctionCall(TypedDict):
    """Function call type definition."""

    arguments: Required[str]
    name: Required[str]


class SystemMessage(TypedDict):
    """System message type definition."""

    role: Required[Literal["system"]]
    content: str
    name: NotRequired[str]


class UserMessage(TypedDict):
    """User message type definition."""

    role: Required[Literal["user"]]
    content: str
    name: NotRequired[str]


class ChatCompletionContentPartImageParam(TypedDict):
    """Image content part for chat completion."""

    type: Required[Literal["image_url"]]
    image_url: Required[dict]


class UserMultiModalMessage(TypedDict):
    """User multimodal message type definition, supports text and image content."""

    role: Required[Literal["user"]]
    content: list[
        ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam
    ]
    name: NotRequired[str]

class UserExplicitCacheMessage(TypedDict):
    """User multimodal message type definition, supports text and image content."""

    role: Required[Literal["user"]]
    content: list[
        ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam
    ]
    name: NotRequired[str]

class AssistantMessage(TypedDict):
    """Assistant message type definition."""

    role: Required[Literal["assistant"]]
    content: str
    name: NotRequired[str]
    tool_calls: Iterable[ChatCompletionMessageToolCallParam]
    function_call: Optional[FunctionCall]
    audio: Optional[Audio]
    reasoning_content: str


LanguageModelMessage: TypeAlias = Union[
    SystemMessage, UserMessage, AssistantMessage, UserMultiModalMessage
]


class ThresholdInfo(TypedDict):
    """阈值信息TypedDict，用于get_threshold_info的返回值。"""

    hard_limit: int
    used_tokens: int
    remaining_tokens: int
    usage_ratio: float


class CumulativeTokenUsage(TypedDict):
    """累计token使用量TypedDict，用于TokenManager中的cumulative_token_usage。"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int


__all__ = [
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "LanguageModelMessage",
    "AgentState",
    "ThresholdInfo",
    "CumulativeTokenUsage",
    "ChatCompletionContentPartTextParam",
    "ChatCompletionContentPartImageParam",
    "UserMultiModalMessage",
]
