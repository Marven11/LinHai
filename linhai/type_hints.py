"""Type definitions for the LinHai project."""

from __future__ import annotations
from typing import Union, Optional, Iterable, TypedDict, Literal
from typing_extensions import Required, TypeAlias

# Agent状态类型
AgentState = Literal["waiting_user", "working", "paused"]


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
    content: Required[Union[str, Iterable[ChatCompletionContentPartTextParam]]]
    name: str


class UserMessage(TypedDict, total=False):
    """User message type definition."""

    role: Required[Literal["user"]]
    content: Required[Union[str, Iterable[ChatCompletionContentPartParam]]]
    name: str


class AssistantMessage(TypedDict, total=False):
    """Assistant message type definition."""

    role: Required[Literal["assistant"]]
    content: Union[str, Iterable[Union[ChatCompletionContentPartTextParam, dict]]]
    name: str
    tool_calls: Iterable[ChatCompletionMessageToolCallParam]
    function_call: Optional[FunctionCall]
    audio: Optional[Audio]


class ToolMessage(TypedDict, total=False):
    """Tool message type definition."""

    role: Required[Literal["tool"]]
    content: Required[Union[str, Iterable[ChatCompletionContentPartTextParam]]]
    tool_call_id: Required[str]


class FunctionMessage(TypedDict, total=False):
    """Function message type definition."""

    role: Required[Literal["function"]]
    content: Required[Optional[str]]
    name: Required[str]


LanguageModelMessage: TypeAlias = Union[
    SystemMessage, UserMessage, AssistantMessage, ToolMessage, FunctionMessage
]

__all__ = [
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "FunctionMessage",
    "LanguageModelMessage",
    "AgentState",
]
