from __future__ import annotations

from math import log2
from typing import TypedDict

from linhai.llm import (
    AnswerTokenUsage,
    EstimateToken,
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
)
from linhai.agent.messages import RuntimeMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.type_hints import CumulativeTokenUsage, ThresholdInfo
from linhai.utils.tokenizer import count_tokens


class MessageTypeCounts(TypedDict):
    user: int
    assistant: int
    system: int
    runtime: int
    other: int


class LongestMessageInfo(TypedDict):
    type_name: str
    tool_name: str | None
    tokens: int


class MessageGroupStatistics(TypedDict):
    count: int
    sparkline: list[float]
    type_counts: MessageTypeCounts
    total_tokens: int
    avg_tokens: float
    longest: LongestMessageInfo | None


class CacheInfo(TypedDict):
    cached_tokens: int
    percentage: float
    is_estimated: bool


class CumulativeCacheStats(TypedDict):
    cache_percentage: float
    avg_input: float
    avg_output: float
    avg_cached: float
    avg_cache_creation: float


class ContextStatistics(TypedDict):
    messages: MessageGroupStatistics
    pinned_messages: MessageGroupStatistics
    notification_messages: MessageGroupStatistics
    large_message_count: int
    hard_limit: int | None
    used_tokens: int | None
    token_limit: int | None
    generation_count: int | None
    cache_info: CacheInfo | None
    cumulative_cache: CumulativeCacheStats | None
    cumulative_total_tokens: int | None
    cumulative_input_tokens: int | None
    cumulative_output_tokens: int | None
    cumulative_cache_miss_count: int | None


def estimate_message_tokens(msg: Message) -> int:
    if isinstance(msg, EstimateToken):
        return msg.estimated_tokens()
    content = msg.get_content()
    if isinstance(content, str):
        return count_tokens(content)
    return 0


def _get_type_key(msg: Message) -> str:
    type_mapping: list[tuple[type, str]] = [
        (UserMessage, "user"),
        (AssistantMessage, "assistant"),
        (SystemMessage, "system"),
        (RuntimeMessage, "runtime"),
    ]
    for msg_class, type_key in type_mapping:
        if isinstance(msg, msg_class):
            return type_key
    return "other"


def _count_message_types(messages: list[Message]) -> MessageTypeCounts:
    counts: MessageTypeCounts = {
        "user": 0,
        "assistant": 0,
        "system": 0,
        "runtime": 0,
        "other": 0,
    }
    for msg in messages:
        counts[_get_type_key(msg)] += 1
    return counts


def _find_longest_message(
    messages: list[Message],
) -> tuple[int, LongestMessageInfo | None]:
    longest_msg: Message | None = None
    longest_tokens = 0
    for msg in messages:
        tokens = estimate_message_tokens(msg)
        if tokens > longest_tokens:
            longest_tokens = tokens
            longest_msg = msg
    if longest_msg is None:
        return 0, None
    type_name = type(longest_msg).__name__
    tool_name: str | None = None
    if isinstance(longest_msg, ToolCallResultMessage):
        tool_name = longest_msg.tool_name
    return longest_tokens, LongestMessageInfo(
        type_name=type_name,
        tool_name=tool_name,
        tokens=longest_tokens,
    )


def compute_message_group_stats(messages: list[Message]) -> MessageGroupStatistics:
    count = len(messages)
    sparkline = [float(log2(estimate_message_tokens(msg) + 1)) for msg in messages]
    total_tokens = sum(estimate_message_tokens(msg) for msg in messages)
    avg_tokens = total_tokens / count if count > 0 else 0.0
    type_counts = _count_message_types(messages)
    _, longest = _find_longest_message(messages)
    return MessageGroupStatistics(
        count=count,
        sparkline=sparkline,
        type_counts=type_counts,
        total_tokens=total_tokens,
        avg_tokens=avg_tokens,
        longest=longest,
    )


def compute_cache_info(
    current_token_usage: AnswerTokenUsage | None,
    used_tokens: int,
) -> CacheInfo | None:
    if current_token_usage is None:
        return None
    actual = current_token_usage.cached_input_tokens
    is_estimated = actual is None
    cached = (
        actual
        if actual is not None
        else (current_token_usage.estimated_cached_input_tokens or 0)
    )
    if cached > 0 and used_tokens > 0:
        return CacheInfo(
            cached_tokens=cached,
            percentage=cached / used_tokens * 100,
            is_estimated=is_estimated,
        )
    if cached > 0:
        return CacheInfo(
            cached_tokens=cached,
            percentage=0.0,
            is_estimated=is_estimated,
        )
    return CacheInfo(
        cached_tokens=0,
        percentage=0.0,
        is_estimated=is_estimated,
    )


def compute_cumulative_cache_stats(
    cumulative: CumulativeTokenUsage,
) -> CumulativeCacheStats:
    message_count = cumulative["message_count"]
    avg_input = cumulative["input_tokens"] / message_count
    avg_output = cumulative["output_tokens"] / message_count
    avg_cached = cumulative["cached_input_tokens"] / message_count
    avg_cache_creation = cumulative["cache_creation_input_tokens"] / message_count
    cache_percentage = avg_cached / avg_input * 100 if avg_input > 0 else 0.0
    return CumulativeCacheStats(
        cache_percentage=cache_percentage,
        avg_input=avg_input,
        avg_output=avg_output,
        avg_cached=avg_cached,
        avg_cache_creation=avg_cache_creation,
    )


def compute_context_statistics(
    messages: list[Message],
    pinned_messages: list[Message],
    notification_entries: list[Message],
    large_message_count: int,
    threshold_info: ThresholdInfo | None,
    token_limit: int | None,
    generation_count: int | None,
    current_token_usage: AnswerTokenUsage | None,
    cumulative_token_usage: CumulativeTokenUsage | None,
) -> ContextStatistics:
    msg_stats = compute_message_group_stats(messages)
    pinned_stats = compute_message_group_stats(pinned_messages)
    notif_stats = compute_message_group_stats(notification_entries)

    hard_limit: int | None = None
    used_tokens: int | None = None
    if threshold_info is not None:
        hard_limit = threshold_info["hard_limit"]
        used_tokens = threshold_info["used_tokens"]

    cache_info: CacheInfo | None = None
    if used_tokens is not None:
        cache_info = compute_cache_info(current_token_usage, used_tokens)

    cumulative_cache: CumulativeCacheStats | None = None
    cumulative_total_tokens: int | None = None
    cumulative_input_tokens: int | None = None
    cumulative_output_tokens: int | None = None
    cumulative_cache_miss_count: int | None = None
    if (
        cumulative_token_usage is not None
        and cumulative_token_usage["message_count"] > 0
    ):
        cumulative_cache = compute_cumulative_cache_stats(cumulative_token_usage)
        cumulative_total_tokens = cumulative_token_usage["total_tokens"]
        cumulative_input_tokens = cumulative_token_usage["input_tokens"]
        cumulative_output_tokens = cumulative_token_usage["output_tokens"]
        cumulative_cache_miss_count = cumulative_token_usage["cache_miss_count"]

    return ContextStatistics(
        messages=msg_stats,
        pinned_messages=pinned_stats,
        notification_messages=notif_stats,
        large_message_count=large_message_count,
        hard_limit=hard_limit,
        used_tokens=used_tokens,
        token_limit=token_limit,
        generation_count=generation_count,
        cache_info=cache_info,
        cumulative_cache=cumulative_cache,
        cumulative_total_tokens=cumulative_total_tokens,
        cumulative_input_tokens=cumulative_input_tokens,
        cumulative_output_tokens=cumulative_output_tokens,
        cumulative_cache_miss_count=cumulative_cache_miss_count,
    )
