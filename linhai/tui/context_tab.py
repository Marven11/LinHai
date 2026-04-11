"""Context tab widget for displaying message statistics and token usage."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Label, ProgressBar, Sparkline, Static

from linhai.context_statistics import (
    ContextStatistics,
    LongestMessageInfo,
    compute_context_statistics,
    compute_notification_details,
)
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent import Agent
from linhai.token_manager import TokenManager

from linhai.registry import Registry


def _format_longest_message(longest: LongestMessageInfo | None) -> str:
    if longest is None:
        return "最长消息: 未知, 0 token"
    type_display = longest["type_name"]
    if longest["tool_name"] is not None:
        type_display += f", 来自{longest['tool_name']}"
    return f"最长消息: {type_display}, {longest['tokens']} token"


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
        scrollbar-size-vertical: 1;
    }

    ContextTabWidget .title {
        margin: 1 0;
        text-style: bold;
    }

    ContextTabWidget Collapsible {
        padding-right: 3;
        padding-bottom: 1;
    }

    ContextTabWidget Sparkline {
        margin-bottom: 1;
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
    ContextTabWidget #notification-list-text {
        height: auto;
    }
    """

    def __init__(self, registry: Registry) -> None:
        super().__init__()
        self.registry: Registry = registry
        self.refresh_interval = 1.0

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            with Collapsible(
                title="消息统计", id="msg-stats-collapsible", collapsed=False
            ):
                yield Label("普通消息", classes="title")
                yield Sparkline(id="msg-stats-sparkline", summary_function=max)
                yield Static(id="msg-stats-text")
                yield Label("置顶消息", classes="title")
                yield Sparkline(id="pinned-stats-sparkline", summary_function=max)
                yield Static(id="pinned-stats-text")
                yield Label("通知消息", classes="title")
                yield Static(id="notification-stats-text")
            with Collapsible(
                title="通知消息列表",
                id="notification-list-collapsible",
                collapsed=True,
            ):
                yield Static(id="notification-list-text")
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
            with Collapsible(
                title="Token用量状态",
                id="cumulative-token-collapsible",
                collapsed=False,
            ):
                yield Static(id="cumulative-token-stats-text")

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_display)
        self.update_display()

    def _update_message_statistics(self, stats: ContextStatistics) -> None:
        msg = stats["messages"]
        sparkline = self.query_one("#msg-stats-sparkline", Sparkline)
        sparkline.data = msg["sparkline"]

        stats_text = self.query_one("#msg-stats-text", Static)
        stats_text.update(
            "总消息数: " + str(msg["count"]) + "\n"
            "平均长度: "
            + f"{msg['avg_tokens']:.1f} token"
            + "\n"
            + _format_longest_message(msg["longest"])
            + "\n"
            "大消息数量: " + str(stats["large_message_count"])
        )

    def _update_pinned_message_statistics(self, stats: ContextStatistics) -> None:
        pinned = stats["pinned_messages"]
        sparkline = self.query_one("#pinned-stats-sparkline", Sparkline)
        sparkline.data = pinned["sparkline"]

        stats_text = self.query_one("#pinned-stats-text", Static)
        if pinned["count"] == 0:
            stats_text.update("无置顶消息")
            return
        stats_text.update(
            "总消息数: " + str(pinned["count"]) + "\n"
            "平均长度: " + f"{pinned['avg_tokens']:.1f} token"
        )

    def _update_notification_message_statistics(self, stats: ContextStatistics) -> None:
        notif = stats["notification_messages"]
        stats_text = self.query_one("#notification-stats-text", Static)
        if notif["count"] == 0:
            stats_text.update("无通知消息")
            return
        stats_text.update(
            "总消息数: " + str(notif["count"]) + "\n"
            "平均长度: "
            + f"{notif['avg_tokens']:.1f} token"
            + "\n"
            + _format_longest_message(notif["longest"])
        )

    def _update_notification_details(self, stats: ContextStatistics) -> None:
        notif_list_text = self.query_one("#notification-list-text", Static)
        details = stats["notification_details"]
        if not details:
            notif_list_text.update("无通知消息")
            return
        lines: list[str] = []
        for item in details:
            lines.append(f"[{item['source']}] ({item['token_count']} token)")
            lines.append(f"  {item['display_content']}")
        notif_list_text.update("\n".join(lines))

    def _update_token_usage(self, stats: ContextStatistics) -> None:
        pb_hard = self.query_one("#pb-hard-limit", ProgressBar)
        pb_model = self.query_one("#pb-model-limit", ProgressBar)
        token_stats_text = self.query_one("#token-stats-text", Static)

        if stats["hard_limit"] is None or stats["used_tokens"] is None:
            token_stats_text.update("不可用")
            return

        used = stats["used_tokens"]
        pb_hard.update(total=float(stats["hard_limit"]), progress=float(used))

        token_limit = stats["token_limit"]
        if token_limit is not None and token_limit > 0:
            pb_model.update(total=float(token_limit), progress=float(used))
        else:
            pb_model.update(total=100.0, progress=float(min(used, 100)))

        generation_count = stats["generation_count"]
        if generation_count is not None:
            generation_line = f"回答生成次数: {generation_count}"
        else:
            generation_line = "回答生成次数: 不可用"

        lines = [
            f"当前用量: {used}",
            f"Token限制: {token_limit}",
            generation_line,
        ]
        cache_info = stats["cache_info"]
        if cache_info is not None and cache_info["cached_tokens"] > 0:
            label = "估算" if cache_info["is_estimated"] else "实际"
            lines.append(
                f"当前消息缓存状态（{label}）: {cache_info['cached_tokens']} token ({cache_info['percentage']:.1f}%)"
            )
        token_stats_text.update("\n".join(lines))

    def _update_cache_status(self, stats: ContextStatistics) -> None:
        pb_cache = self.query_one("#pb-cache-ratio", ProgressBar)
        cache_stats_text = self.query_one("#cache-stats-text", Static)

        cumulative_cache = stats["cumulative_cache"]
        if cumulative_cache is None:
            cache_stats_text.update("暂无数据")
            return

        cache_percentage = cumulative_cache["cache_percentage"]
        pb_cache.update(total=100.0, progress=cache_percentage)

        cache_stats_text.update(
            f"平均缓存比例: {cache_percentage:.1f}%\n"
            f"平均输入Token: {cumulative_cache['avg_input']:.0f}\n"
            f"平均输出Token: {cumulative_cache['avg_output']:.0f}\n"
            f"平均缓存Token: {cumulative_cache['avg_cached']:.0f}\n"
            f"平均缓存创建Token: {cumulative_cache['avg_cache_creation']:.0f}"
        )

    def _update_cumulative_token_usage(self, stats: ContextStatistics) -> None:
        cumulative_stats_text = self.query_one("#cumulative-token-stats-text", Static)

        if stats["cumulative_total_tokens"] is None:
            cumulative_stats_text.update("暂无数据")
            return

        cumulative_stats_text.update(
            f"累计Token用量: {stats['cumulative_total_tokens']}\n"
            f"累计输入Token用量: {stats['cumulative_input_tokens']}\n"
            f"累计输出Token用量: {stats['cumulative_output_tokens']}\n"
            f"缓存失效次数: {stats['cumulative_cache_miss_count']}"
        )

    def update_display(self) -> None:
        agent_message: AgentMessage = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        orchestration: AgentContextOrchestration = self.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )
        agent: Agent = self.registry.get_member_typechecked("agent", Agent)

        messages = agent_message.messages
        pinned_messages = agent_message.pinned_messages
        notification_entries = list(
            entry["message"] for entry in agent_message.notification_messages.values()
        )

        threshold_info = agent.get_threshold_info()
        _, current_llm = agent.get_current_llm_info()
        token_limit = current_llm.get_token_limit()

        from linhai.base import AnswerTokenUsage
        from linhai.type_hints import CumulativeTokenUsage

        current_token_usage: AnswerTokenUsage | None = None
        generation_count: int | None = None
        cumulative_token_usage: CumulativeTokenUsage | None = None

        if self.registry.has_member("token_manager"):
            token_manager = self.registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            current_token_usage = token_manager.current_token_usage
            generation_count = token_manager.generation_count
            cumulative_token_usage = token_manager.cumulative_token_usage

        notification_details = compute_notification_details(
            agent_message.notification_messages
        )

        stats = compute_context_statistics(
            messages=messages,
            pinned_messages=pinned_messages,
            notification_entries=notification_entries,
            notification_details=notification_details,
            large_message_count=len(orchestration.large_messages),
            threshold_info=threshold_info,
            token_limit=token_limit,
            generation_count=generation_count,
            current_token_usage=current_token_usage,
            cumulative_token_usage=cumulative_token_usage,
        )

        self._update_cumulative_token_usage(stats)
        self._update_message_statistics(stats)
        self._update_pinned_message_statistics(stats)
        self._update_notification_message_statistics(stats)
        self._update_notification_details(stats)
        self._update_token_usage(stats)
        self._update_cache_status(stats)
