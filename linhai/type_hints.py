"""
传给OpenAI的LLM Message定义等

我们完全弃用OpenAI的工具调用功能
"""

from __future__ import annotations
from typing import Union, Optional, Iterable, TypedDict, Literal
from typing_extensions import Required, TypeAlias, NotRequired

AgentState = Literal["waiting_user", "working", "sleeping"]


class ChatCompletionContentPartTextParam(TypedDict):
    """Parameters for text content part in chat completion."""

    text: Required[str]
    type: Required[Literal["text"]]
    cache_control: NotRequired[dict]


class ChatCompletionMessageToolCallParam(TypedDict):
    """Parameters for tool call in chat completion."""

    id: Required[str]
    function: Required[FunctionCall]
    type: Required[Literal["function"]]


class OpenAiToolCall(TypedDict):
    """OpenAI原生工具调用，兼容ChatCompletionMessageFunctionToolCallParam。"""

    id: Required[str]
    function: Required[FunctionCall]
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
    tool_calls: NotRequired[Iterable[ChatCompletionMessageToolCallParam]]
    function_call: NotRequired[Optional[FunctionCall]]
    audio: NotRequired[Optional[Audio]]
    reasoning_content: NotRequired[str]


class ToolResultMsg(TypedDict):
    """Tool result message for OpenAI native tool calling."""

    role: Required[Literal["tool"]]
    tool_call_id: Required[str]
    content: Required[str]


LanguageModelMessage: TypeAlias = Union[
    SystemMessage, UserMessage, AssistantMessage, UserMultiModalMessage, ToolResultMsg
]


class ThresholdInfo(TypedDict):
    """阈值信息TypedDict，用于get_threshold_info的返回值。"""

    hard_limit: int
    used_tokens: int
    remaining_tokens: int
    usage_ratio: float


class WithSecret(TypedDict):
    """with_secret参数的TypedDict，分别控制参数替换和结果掩码。"""

    in_arguments: list[str]
    in_result: list[str]


class ToolCallDict(TypedDict):
    """工具调用TypedDict，用于extract_tool_calls_with_errors的返回值。"""

    name: str
    arguments: dict
    assert_success: NotRequired[bool]
    with_secret: NotRequired[WithSecret]


class CumulativeTokenUsage(TypedDict):
    """累计token使用量TypedDict，用于TokenManager中的cumulative_token_usage。"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    cache_creation_input_tokens: int
    message_count: int
    cache_miss_count: int


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
    "ToolCallDict",
    "ToolResultMsg",
    "WithSecret",
]
