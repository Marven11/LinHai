"""
传给OpenAI的LLM Message定义等

我们完全弃用OpenAI的工具调用功能
"""

from __future__ import annotations
from typing import Union, Optional, Iterable, TypedDict, Literal
from typing_extensions import Required, TypeAlias

AgentState = Literal["waiting_user", "working"]


class ChatCompletionContentPartTextParam(TypedDict):
    """Parameters for text content part in chat completion."""

    text: Required[str]
    type: Required[Literal["text"]]


class ChatCompletionContentPartParam(TypedDict):
    """Parameters for content part in chat completion."""

    text: Required[str]
    type: Required[Literal["text"]]


class ChatCompletionMessageToolCallParam(TypedDict):
    """Parameters for tool call in chat completion."""

    id: Required[str]
    function: Required[dict]
    type: Required[Literal["function"]]


class Audio(TypedDict, total=False):
    """Audio data type definition."""

    id: Required[str]


class FunctionCall(TypedDict, total=False):
    """Function call type definition."""

    arguments: Required[str]
    name: Required[str]


class SystemMessage(TypedDict, total=False):
    """System message type definition."""

    role: Required[Literal["system"]]
    content: str
    name: str


class UserMessage(TypedDict, total=False):
    """User message type definition."""

    role: Required[Literal["user"]]
    content: str
    name: str


class AssistantMessage(TypedDict, total=False):
    """Assistant message type definition."""

    role: Required[Literal["assistant"]]
    content: str
    name: str
    tool_calls: Iterable[ChatCompletionMessageToolCallParam]
    function_call: Optional[FunctionCall]
    audio: Optional[Audio]


LanguageModelMessage: TypeAlias = Union[SystemMessage, UserMessage, AssistantMessage]


class ThresholdInfo(TypedDict):
    """阈值信息TypedDict，用于get_threshold_info的返回值。"""

    hard_limit: int
    used_tokens: int
    remaining_tokens: int
    usage_ratio: float


__all__ = [
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "LanguageModelMessage",
    "AgentState",
    "ThresholdInfo",
]
