"""Context tab widget for displaying message statistics and token usage."""

from functools import lru_cache
from typing import Optional, TypedDict

import tiktoken
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Label, ProgressBar, Sparkline, Static

from linhai.llm import (
    AnswerTokenUsage,
    EstimateToken,
    UserMessage,
    AssistantMessage,
    SystemMessage,
)
from linhai.agent.base import RuntimeMessage
from linhai.tool.base import ToolCallResultMessage

from linhai.registry import Registry
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent import Agent
from linhai.llm import Message
from linhai.token_manager import TokenManager

_tokenizer: tiktoken.Encoding | None = None


def _get_tokenizer() -> tiktoken.Encoding:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding("cl100k_base")
    return _tokenizer


@lru_cache(maxsize=1000)
def _count_tokens_cached(text: str) -> int:
    return len(_get_tokenizer().encode(text))


class MessageTypeCounts(TypedDict):
    """Type definition for message type counts."""

    user: int
    assistant: int
    system: int
    runtime: int
    other: int


class ContextTabWidget(Static):
    """Widget for displaying context information: message stats, token usage, etc."""

    DEFAULT_CSS = """
    ContextTabWidget {
        width: 100%;
        height: 100%;
        background: #2E3440;
    }

    ContextTabWidget VerticalScroll {
        padding-right: 1;
    }

    ContextTabWidget #msg-stats-sparkline {
        height: 3;
    }

    ContextTabWidget #token-usage-collapsible {
        height: auto;
    }

    ContextTabWidget .token-usage-label {
        height: 1;
        color: $text-muted;
    }

    ContextTabWidget #token-stats-text {
        height: auto;
    }

    ContextTabWidget #cache-status-collapsible {
        height: auto;
    }

    ContextTabWidget #cache-stats-text {
        height: auto;
    }
    """

    def __init__(self, registry: Registry) -> None:
        super().__init__()
        self.registry: Registry = registry
        self.refresh_interval = 1.0  # seconds

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            with Collapsible(
                title="消息统计", id="msg-stats-collapsible", collapsed=False
            ):
                yield Sparkline(id="msg-stats-sparkline", summary_function=max)
                yield Static(id="msg-stats-text")
            with Collapsible(
                title="上下文Token用量", id="token-usage-collapsible", collapsed=False
            ):
                yield Label("相对硬限制", classes="token-usage-label")
                yield ProgressBar(id="pb-hard-limit", show_eta=False)
                yield Label("相对模型限制", classes="token-usage-label")
                yield ProgressBar(id="pb-model-limit", show_eta=False)
                yield Static(id="token-stats-text")
            with Collapsible(
                title="缓存状态", id="cache-status-collapsible", collapsed=False
            ):
                yield ProgressBar(id="pb-cache-ratio", show_eta=False)
                yield Static(id="cache-stats-text")

    def on_mount(self) -> None:
        """Start periodic refresh."""
        self.set_interval(self.refresh_interval, self.update_display)
        self.update_display()

    def on_unmount(self) -> None:
        """Clean up resources when unmounted."""
        # No resources to clean up with simple progress bar implementation

    def _estimate_message_tokens(self, msg: Message) -> int:
        if isinstance(msg, EstimateToken):
            return msg.estimated_tokens()
        content = msg.get_content()
        if isinstance(content, str):
            return _count_tokens_cached(content)
        return 0

    def _count_message_types(
        self, messages: list[Message]
    ) -> tuple[MessageTypeCounts, int, int, Optional[Message]]:
        type_mapping: list[tuple[type, str]] = [
            (UserMessage, "user"),
            (AssistantMessage, "assistant"),
            (SystemMessage, "system"),
            (RuntimeMessage, "runtime"),
        ]

        type_counts: MessageTypeCounts = {
            "user": 0,
            "assistant": 0,
            "system": 0,
            "runtime": 0,
            "other": 0,
        }
        total_tokens = 0
        max_tokens_msg: Optional[Message] = None
        max_tokens = 0

        for msg in messages:
            tokens = self._estimate_message_tokens(msg)
            total_tokens += tokens
            if tokens > max_tokens:
                max_tokens = tokens
                max_tokens_msg = msg

            matching_type = next(
                (
                    type_key
                    for msg_class, type_key in type_mapping
                    if isinstance(msg, msg_class)
                ),
                None,
            )
            if matching_type:
                type_counts[matching_type] += 1
            else:
                type_counts["other"] += 1

        return type_counts, total_tokens, max_tokens, max_tokens_msg

    def _get_token_cache_info(self, used: int) -> tuple[int, float]:
        """Get cached token information from token manager.

        Args:
            used: Total tokens used (input + output)

        Returns:
            Tuple of (cached_tokens: int, cache_percentage: float)
        """
        if not self.registry.has_member("token_manager"):
            raise RuntimeError("token_manager should be registered in registry")

        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )

        # Fail fast: token_usage must be AnswerTokenUsage or None
        token_usage = token_manager.current_token_usage
        if token_usage is None:
            return 0, 0.0

        # Fail fast: if not None, must be AnswerTokenUsage
        if not isinstance(token_usage, AnswerTokenUsage):
            raise RuntimeError(
                f"token_manager.current_token_usage should be AnswerTokenUsage or None, got {type(token_usage)}"
            )

        cached = token_usage.cached_input_tokens or 0
        if cached > 0 and used > 0:
            return cached, (cached / used * 100)
        elif cached > 0:
            return cached, 0.0

        return 0, 0.0

    def _update_message_statistics(
        self, messages: list[Message], large_message_count: int
    ) -> None:
        sparkline = self.query_one("#msg-stats-sparkline", Sparkline)
        sparkline.data = [float(self._estimate_message_tokens(msg)) for msg in messages]

        message_count = len(messages)
        _, total_tokens, max_tokens, max_tokens_msg = self._count_message_types(
            messages
        )
        avg_tokens = total_tokens / message_count if message_count > 0 else 0

        type_display = "未知"
        if max_tokens_msg is not None:
            type_display = type(max_tokens_msg).__name__
            if isinstance(max_tokens_msg, ToolCallResultMessage):
                type_display += f", 来自{max_tokens_msg.tool_name}"

        stats_text = self.query_one("#msg-stats-text", Static)
        stats_text.update(
            "总消息数: " + str(message_count) + "\n"
            "消息平均Token数: " + f"{avg_tokens:.1f}" + "\n"
            "最长消息Token数: " + str(max_tokens) + " (" + type_display + ")\n"
            "大消息数量: " + str(large_message_count)
        )

    def _update_cache_status(self) -> None:
        pb_cache = self.query_one("#pb-cache-ratio", ProgressBar)
        cache_stats_text = self.query_one("#cache-stats-text", Static)

        if not self.registry.has_member("token_manager"):
            cache_stats_text.update("TokenManager未注册")
            return

        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        cumulative = token_manager.cumulative_token_usage

        if cumulative is None:
            cache_stats_text.update("暂无数据")
            return

        message_count = cumulative["message_count"]
        if message_count == 0:
            cache_stats_text.update("暂无数据")
            return

        avg_input = cumulative["input_tokens"] / message_count
        avg_output = cumulative["output_tokens"] / message_count
        avg_cached = cumulative["cached_input_tokens"] / message_count
        avg_cache_creation = cumulative["cache_creation_input_tokens"] / message_count

        if avg_input > 0:
            cache_percentage = avg_cached / avg_input * 100
        else:
            cache_percentage = 0.0

        pb_cache.update(total=100.0, progress=cache_percentage)

        cache_stats_text.update(
            f"平均缓存比例: {cache_percentage:.1f}%\n"
            f"平均输入Token: {avg_input:.0f}\n"
            f"平均输出Token: {avg_output:.0f}\n"
            f"平均缓存Token: {avg_cached:.0f}\n"
            f"平均缓存创建Token: {avg_cache_creation:.0f}"
        )

    def _update_token_usage(self, agent: Agent) -> None:
        pb_hard = self.query_one("#pb-hard-limit", ProgressBar)
        pb_model = self.query_one("#pb-model-limit", ProgressBar)
        token_stats_text = self.query_one("#token-stats-text", Static)

        if not agent:
            token_stats_text.update("Agent未初始化")
            return

        threshold_info = agent.get_threshold_info()
        if not threshold_info:
            token_stats_text.update("不可用")
            return

        hard = threshold_info["hard_limit"]
        used = threshold_info["used_tokens"]

        pb_hard.update(total=float(hard), progress=float(used))

        _, current_llm = agent.get_current_llm_info()
        token_limit = current_llm.get_token_limit()

        if token_limit is not None and token_limit > 0:
            pb_model.update(total=float(token_limit), progress=float(used))
        else:
            pb_model.update(total=100.0, progress=float(min(used, 100)))

        cached, cache_percentage = self._get_token_cache_info(int(used))

        lines = [
            f"当前用量: {used}",
            f"Token限制: {token_limit}",
        ]
        if cached > 0:
            lines.append(
                f"当前消息估算缓存Token数: {cached} (~{cache_percentage:.1f}%)"
            )
        token_stats_text.update("\n".join(lines))

    def update_display(self) -> None:
        """Update the display with current context information."""
        agent_message: AgentMessage = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )

        orchestration: AgentContextOrchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )
        agent: Agent = self.registry.get_member_typechecked("agent", Agent)

        messages = agent_message.messages

        self._update_message_statistics(messages, len(orchestration.large_messages))
        self._update_token_usage(agent)
        self._update_cache_status()
