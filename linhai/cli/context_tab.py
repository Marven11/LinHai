"""Context tab widget for displaying message statistics and token usage."""

import reprlib
from typing import Optional, TypedDict

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Sparkline, Static

# 导入AnswerTokenUsage用于token用量显示
from linhai.llm import AnswerTokenUsage, UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage
from linhai.tool.base import ToolCallResultMessage

from linhai.registry import Registry
from linhai.agent.message import AgentMessage, NotificationMessageEntry
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent import Agent
from linhai.llm import Message
from linhai.token_manager import TokenManager


reprobj = reprlib.Repr(maxstring=60)


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

    ContextTabWidget #msg-stats-sparkline {
        height: 3;
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
            yield Static(id="context-content")

    def on_mount(self) -> None:
        """Start periodic refresh."""
        self.set_interval(self.refresh_interval, self.update_display)
        self.update_display()

    def on_unmount(self) -> None:
        """Clean up resources when unmounted."""
        # No resources to clean up with simple progress bar implementation

    def _count_message_types(
        self, messages: list[Message]
    ) -> tuple[MessageTypeCounts, int, int, Optional[Message]]:
        """Count message types and calculate statistics.

        Args:
            messages: List of messages

        Returns:
            Tuple of (type_counts, total_chars, max_length, max_length_msg)
        """

        # Define message type mapping to avoid hardcoded keys
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
        total_chars = 0
        max_length_msg: Optional[Message] = None
        max_length = 0

        for msg in messages:
            content = str(msg)
            length = len(content)
            total_chars += length
            if length > max_length:
                max_length = length
                max_length_msg = msg

            # Simplified type checking using next() with generator
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

        return type_counts, total_chars, max_length, max_length_msg

    def _create_progress_bar(self, percentage: float) -> str:
        """Create a text progress bar using block characters.

        Args:
            percentage: Percentage value (0-100)

        Returns:
            String representation of progress bar
        """
        # Use block characters for simple yet effective progress bar
        # This is appropriate for text display in Static widget
        bar_width = 30
        filled_width = int(bar_width * percentage / 100)
        empty_width = bar_width - filled_width

        # Use block characters for better visual
        filled = "█" * filled_width
        empty = "░" * empty_width

        return f"[{filled}{empty}] {percentage:.1f}%"

    def _get_token_cache_info(self, used: int) -> tuple[int, float]:
        """Get cached token information from token manager.

        Args:
            used: Total tokens used (input + output)

        Returns:
            Tuple of (cached_tokens: int, cache_percentage: float)
        """
        if not self.registry.has_member("token_manager"):
            raise RuntimeError("token_manager should be registered in registry")

        from linhai.token_manager import TokenManager

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
        sparkline.data = [float(len(str(msg))) for msg in messages]

        message_count = len(messages)
        _, total_chars, max_length, max_length_msg = self._count_message_types(messages)
        avg_length = total_chars / message_count if message_count > 0 else 0

        type_display = "未知"
        if max_length_msg is not None:
            type_display = type(max_length_msg).__name__
            if isinstance(max_length_msg, ToolCallResultMessage):
                type_display += f", 来自{max_length_msg.tool_name}"

        stats_text = self.query_one("#msg-stats-text", Static)
        stats_text.update(
            "总消息数: " + str(message_count) + "\n"
            "消息平均长度: " + f"{avg_length:.1f}" + " 字符\n"
            "最长消息长度: " + str(max_length) + " 字符 (" + type_display + ")\n"
            "大消息数量: " + str(large_message_count)
        )

    def _build_token_usage_section(self, grid: Table, agent: Agent) -> None:
        """Build token usage section."""
        grid.add_row(Text("Token用量", style="bold yellow"))
        grid.add_row("")

        if not agent:
            grid.add_row("Token信息:", "Agent未初始化")
            grid.add_row("")
            return

        threshold_info = agent.get_threshold_info()
        if not threshold_info:
            grid.add_row("Token信息:", "不可用")
            grid.add_row("")
            return

        # threshold_info是ThresholdInfo类型的字典
        hard = threshold_info["hard_limit"]
        used = threshold_info["used_tokens"]
        taken = threshold_info["usage_ratio"]
        percentage = taken * 100

        # Create proper progress bar using Rich
        progress_bar_text = self._create_progress_bar(float(percentage))

        grid.add_row("当前用量:", f"{used}")
        grid.add_row("硬限制:", f"{hard}")
        grid.add_row("使用率:", progress_bar_text)

        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        if token_manager.current_token_usage is not None:
            token_usage = token_manager.current_token_usage
            grid.add_row("输入token:", f"{token_usage.input_tokens}")
            grid.add_row("输出token:", f"{token_usage.output_tokens}")
            grid.add_row("总token:", f"{token_usage.total_tokens}")

        cached, cache_percentage = self._get_token_cache_info(int(used))
        if cached > 0:
            grid.add_row("缓存token:", f"{cached} (~{cache_percentage:.1f}%)")

        grid.add_row("")

    def _build_orchestration_section(
        self, grid: Table, orchestration: AgentContextOrchestration
    ) -> None:
        """Build orchestration status section."""
        grid.add_row(Text("编排状态", style="bold yellow"))
        grid.add_row("")

        large_messages = orchestration.large_messages

        # 显示大消息repr列表
        if large_messages:
            grid.add_row(Text(f"当前有{len(large_messages)}条大消息", style="bold"))
            # 获取大消息的repr列表，最多显示3条
            repr_list = []
            for msg in list(orchestration.large_messages)[:3]:
                repr_list.append(reprlib.Repr(maxstring=60).repr(str(msg)))
            for i, repr_msg in enumerate(repr_list, 1):
                grid.add_row(f"  {i}.", repr_msg)
            if len(large_messages) > 3:
                grid.add_row("提示:", f"... 还有{len(large_messages) - 3}条未显示")
            grid.add_row(
                "提示:", "调用context_forget_large_message可清理大消息（需≥5条）"
            )

        grid.add_row("")

    def _build_recent_messages_section(
        self, grid: Table, messages: list[Message]
    ) -> None:
        """Build recent messages section."""
        grid.add_row(Text("最近消息 (最多5条)", style="bold yellow"))
        grid.add_row("")

        recent_messages = messages[-5:] if messages else []
        for i, msg in enumerate(recent_messages, 1):
            index = len(messages) - len(recent_messages) + i
            msg_type = type(msg).__name__
            preview = reprobj.repr(str(msg))[:50]
            grid.add_row(f"{index}. {msg_type}:", preview)

        grid.add_row("")

    def _build_notification_messages_section(
        self, grid: Table, notification_messages: dict[str, NotificationMessageEntry]
    ) -> None:
        """Build notification messages section."""
        grid.add_row(Text("通知消息", style="bold yellow"))
        grid.add_row("")

        if not notification_messages:
            grid.add_row("无通知消息")
        else:
            for source, entry in notification_messages.items():
                msg = entry["message"]
                msg_type = type(msg).__name__
                preview = reprobj.repr(str(msg))[:80]  # Show more content
                grid.add_row(f"{source} ({msg_type}):", preview)
        grid.add_row("")

    def update_display(self) -> None:
        """Update the display with current context information."""
        agent_message: AgentMessage = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        from linhai.agent.orchestration import AgentContextOrchestration

        orchestration: AgentContextOrchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )
        agent: Agent = self.registry.get_member_typechecked("agent", Agent)

        messages = agent_message.messages

        self._update_message_statistics(messages, len(orchestration.large_messages))

        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan")
        grid.add_column()

        self._build_token_usage_section(grid, agent)
        self._build_orchestration_section(grid, orchestration)
        self._build_recent_messages_section(grid, messages)
        self._build_notification_messages_section(
            grid, agent_message.notification_messages
        )

        self._update_content_widget(grid)

    def _show_waiting_message(self) -> None:
        """Show waiting message during initialization."""
        content = "等待组件初始化..."
        content_widget = self.query_one("#context-content")
        if isinstance(content_widget, Static):
            content_widget.update(content)  # type: ignore[attr-defined]

    def _update_content_widget(self, content: Table) -> None:
        """Update the content widget with the given content."""
        content_widget = self.query_one("#context-content")
        if isinstance(content_widget, Static):
            content_widget.update(content)  # type: ignore[attr-defined]
