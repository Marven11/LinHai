"""Context tab widget for displaying message statistics and token usage."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import (
    Collapsible,
    DataTable,
    Label,
    ProgressBar,
    Sparkline,
    Static,
)

from rich.text import Text

from linhai.context_statistics import (
    ContextStatistics,
    LongestMessageInfo,
    compute_context_statistics,
    compute_notification_details,
    estimate_message_tokens,
)

from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import (
    AgentContextOrchestration,
    check_cleanable_threshold,
    get_cleanable_large_messages,
)
from linhai.agent import Agent
from linhai.base import SystemMessage
from linhai.token_manager import TokenManager

from linhai.registry import Registry
from linhai.utils.i18n import t


def _format_longest_message(longest: LongestMessageInfo | None) -> str:
    if longest is None:
        return t(
            {
                "zh_CN": "最长消息: 未知, 0 token",
                "en": "Longest message: unknown, 0 token",
            }
        )
    type_display = longest["type_name"]
    if longest["tool_name"] is not None:
        type_display += f", {t({'zh_CN': '来自', 'en': 'from'})}{longest['tool_name']}"
    return f"{t({'zh_CN': '最长消息', 'en': 'Longest message'})}: {type_display}, {longest['tokens']} token"


class ContextTabWidget(Static):
    """Widget for displaying context information: message stats, token usage, etc."""

    DEFAULT_CSS = """
    ContextTabWidget {
        width: 100%;
        height: 100%;
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
    ContextTabWidget #recent-cache-table {
        height: auto;
        overflow: hidden;
    }
    ContextTabWidget #recent-cache-collapsible {
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
                title=t({"zh_CN": "消息统计", "en": "Message Statistics"}),
                id="msg-stats-collapsible",
                collapsed=False,
            ):
                yield Label(
                    t({"zh_CN": "普通消息", "en": "Normal Messages"}), classes="title"
                )
                yield Sparkline(id="msg-stats-sparkline", summary_function=max)
                yield Static(id="msg-stats-text")
                yield Label(
                    t({"zh_CN": "置顶消息", "en": "Pinned Messages"}), classes="title"
                )
                yield Sparkline(id="pinned-stats-sparkline", summary_function=max)
                yield Static(id="pinned-stats-text")
                yield Label(
                    t({"zh_CN": "通知消息", "en": "Notification Messages"}),
                    classes="title",
                )
                yield Static(id="notification-stats-text")
            with Collapsible(
                title=t({"zh_CN": "通知消息列表", "en": "Notification List"}),
                id="notification-list-collapsible",
                collapsed=True,
            ):
                yield Static(id="notification-list-text")
            with Collapsible(
                title=t({"zh_CN": "上下文Token用量", "en": "Context Token Usage"}),
                id="token-usage-collapsible",
                collapsed=False,
            ):
                yield Label(
                    t({"zh_CN": "相对硬限制", "en": "Relative to Hard Limit"}),
                    classes="token-usage-label",
                )
                yield ProgressBar(id="pb-hard-limit", show_eta=False)
                yield Label(
                    t({"zh_CN": "相对模型限制", "en": "Relative to Model Limit"}),
                    classes="token-usage-label",
                )
                yield ProgressBar(id="pb-model-limit", show_eta=False)
                yield Static(id="token-stats-text")
            with Collapsible(
                title=t({"zh_CN": "缓存状态", "en": "Cache Status"}),
                id="cache-status-collapsible",
                collapsed=False,
            ):
                yield ProgressBar(id="pb-cache-ratio", show_eta=False)
                yield Static(id="cache-stats-text")
            with Collapsible(
                title=t({"zh_CN": "Token用量状态", "en": "Token Usage Status"}),
                id="cumulative-token-collapsible",
                collapsed=False,
            ):
                yield Static(id="cumulative-token-stats-text")
            with Collapsible(
                title=t({"zh_CN": "最近缓存状态", "en": "Recent Cache Status"}),
                id="recent-cache-collapsible",
                collapsed=True,
            ):
                yield DataTable(id="recent-cache-table")

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_display)
        self.update_display()

    def _update_message_statistics(self, stats: ContextStatistics) -> None:
        msg = stats["messages"]
        sparkline = self.query_one("#msg-stats-sparkline", Sparkline)
        sparkline.data = msg["sparkline"]

        stats_text = self.query_one("#msg-stats-text", Static)
        stats_text.update(
            t({"zh_CN": "总消息数", "en": "Total messages"})
            + ": "
            + str(msg["count"])
            + "\n"
            + t({"zh_CN": "平均长度", "en": "Average length"})
            + f": {msg['avg_tokens']:.1f} token"
            + "\n"
            + _format_longest_message(msg["longest"])
            + "\n"
            + t({"zh_CN": "大消息数量", "en": "Large messages"})
            + ": "
            + str(stats["large_message_count"])
            + "\n"
            + t({"zh_CN": "可清理大消息", "en": "Cleanable large messages"})
            + ": "
            + str(stats["cleanable_large_message_count"])
            + "\n"
            + t(
                {
                    "zh_CN": "可清理大消息token量",
                    "en": "Cleanable large messages tokens",
                }
            )
            + ": "
            + str(stats["cleanable_large_message_tokens"])
            + "\n"
            + t({"zh_CN": "是否可清理", "en": "Can clean"})
            + ": "
            + (
                t({"zh_CN": "是", "en": "Yes"})
                if stats["can_clean_large_messages"]
                else t({"zh_CN": "否", "en": "No"})
            )
        )

    def _update_pinned_message_statistics(self, stats: ContextStatistics) -> None:
        pinned = stats["pinned_messages"]
        sparkline = self.query_one("#pinned-stats-sparkline", Sparkline)
        sparkline.data = pinned["sparkline"]

        stats_text = self.query_one("#pinned-stats-text", Static)
        if pinned["count"] == 0:
            stats_text.update(t({"zh_CN": "无置顶消息", "en": "No pinned messages"}))
            return
        system_prompt_tokens = stats.get("system_prompt_tokens")
        lines = [
            t({"zh_CN": "总消息数", "en": "Total messages"})
            + ": "
            + str(pinned["count"]),
            t({"zh_CN": "平均长度", "en": "Average length"})
            + f": {pinned['avg_tokens']:.1f} token",
        ]
        if system_prompt_tokens is not None:
            lines.append(
                t({"zh_CN": "System Prompt", "en": "System Prompt"})
                + f": {system_prompt_tokens} token"
            )
        stats_text.update("\n".join(lines))

    def _update_notification_message_statistics(self, stats: ContextStatistics) -> None:
        notif = stats["notification_messages"]
        stats_text = self.query_one("#notification-stats-text", Static)
        if notif["count"] == 0:
            stats_text.update(
                t({"zh_CN": "无通知消息", "en": "No notification messages"})
            )
            return
        stats_text.update(
            t({"zh_CN": "总消息数", "en": "Total messages"})
            + ": "
            + str(notif["count"])
            + "\n"
            + t({"zh_CN": "平均长度", "en": "Average length"})
            + f": {notif['avg_tokens']:.1f} token"
            + "\n"
            + _format_longest_message(notif["longest"])
        )

    def _update_notification_details(self, stats: ContextStatistics) -> None:
        notif_list_text = self.query_one("#notification-list-text", Static)
        details = stats["notification_details"]
        if not details:
            notif_list_text.update(
                t({"zh_CN": "无通知消息", "en": "No notification messages"})
            )
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
            token_stats_text.update(t({"zh_CN": "不可用", "en": "N/A"}))
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
            generation_line = f"{t({'zh_CN': '回答生成次数', 'en': 'Generation count'})}: {generation_count}"
        else:
            generation_line = f"{t({'zh_CN': '回答生成次数', 'en': 'Generation count'})}: {t({'zh_CN': '不可用', 'en': 'N/A'})}"

        lines = [
            f"{t({'zh_CN': '当前用量', 'en': 'Current usage'})}: {used}",
            f"{t({'zh_CN': 'Token限制', 'en': 'Token limit'})}: {token_limit}",
            generation_line,
        ]
        cache_info = stats["cache_info"]
        if cache_info is not None and cache_info["cached_tokens"] > 0:
            label = (
                t({"zh_CN": "估算", "en": "estimated"})
                if cache_info["is_estimated"]
                else t({"zh_CN": "实际", "en": "actual"})
            )
            percentage = cache_info["percentage"]
            abnormal_note = ""
            lines.append(
                f"{t({'zh_CN': '当前消息缓存状态', 'en': 'Current message cache status'})}（{label}）: {cache_info['cached_tokens']} token ({percentage:.1f}%){abnormal_note}"
            )
        token_stats_text.update("\n".join(lines))

    def _update_cache_status(self, stats: ContextStatistics) -> None:
        pb_cache = self.query_one("#pb-cache-ratio", ProgressBar)
        cache_stats_text = self.query_one("#cache-stats-text", Static)

        cumulative_cache = stats["cumulative_cache"]
        if cumulative_cache is None:
            cache_stats_text.update(t({"zh_CN": "暂无数据", "en": "No data"}))
            return

        cache_percentage = cumulative_cache["cache_percentage"]
        pb_cache.update(total=100.0, progress=cache_percentage)

        abnormal_note = ""
        cache_stats_text.update(
            f"{t({'zh_CN': '平均缓存比例', 'en': 'Avg cache ratio'})}: {cache_percentage:.1f}%{abnormal_note}\n"
            f"{t({'zh_CN': '平均输入Token', 'en': 'Avg input tokens'})}: {cumulative_cache['avg_input']:.0f}\n"
            f"{t({'zh_CN': '平均输出Token', 'en': 'Avg output tokens'})}: {cumulative_cache['avg_output']:.0f}\n"
            f"{t({'zh_CN': '平均缓存Token', 'en': 'Avg cached tokens'})}: {cumulative_cache['avg_cached']:.0f}\n"
            f"{t({'zh_CN': '平均缓存创建Token', 'en': 'Avg cache creation tokens'})}: {cumulative_cache['avg_cache_creation']:.0f}"
        )

    def _update_cumulative_token_usage(self, stats: ContextStatistics) -> None:
        cumulative_stats_text = self.query_one("#cumulative-token-stats-text", Static)

        if stats["cumulative_total_tokens"] is None:
            cumulative_stats_text.update(t({"zh_CN": "暂无数据", "en": "No data"}))
            return

        cumulative_stats_text.update(
            f"{t({'zh_CN': '累计Token用量', 'en': 'Cumulative token usage'})}: {stats['cumulative_total_tokens']}\n"
            f"{t({'zh_CN': '累计输入Token用量', 'en': 'Cumulative input tokens'})}: {stats['cumulative_input_tokens']}\n"
            f"{t({'zh_CN': '累计输出Token用量', 'en': 'Cumulative output tokens'})}: {stats['cumulative_output_tokens']}\n"
            f"{t({'zh_CN': '缓存失效次数', 'en': 'Cache miss count'})}: {stats['cumulative_cache_miss_count']}"
        )

    def _update_recent_cache_status(self, stats: ContextStatistics) -> None:
        table = self.query_one("#recent-cache-table", DataTable)
        table.clear()
        recent_rows = stats["recent_cache_rows"]
        if recent_rows is None:
            return

        if len(table.columns) == 0:
            table.add_columns(
                t({"zh_CN": "输入Token", "en": "Input Tokens"}),
                t({"zh_CN": "实际缓存", "en": "Actual Cache"}),
                t({"zh_CN": "估算缓存", "en": "Est. Cache"}),
                t({"zh_CN": "非缓存", "en": "Non-Cached"}),
                t({"zh_CN": "输出Token", "en": "Output Tokens"}),
                t({"zh_CN": "缓存比例", "en": "Cache Ratio"}),
            )

        token_keys = [
            "input_tokens",
            "actual_cached_tokens",
            "estimated_cached_tokens",
            "non_cached_tokens",
            "output_tokens",
        ]
        for row in recent_rows:
            styled_row: list[Text | str] = []
            for key in token_keys:
                val = row[key]
                if val is None:
                    styled_row.append(Text("-"))
                elif val < 1000:
                    styled_row.append(Text(str(val), style="grey50"))
                else:
                    styled_row.append(str(val))
            ratio = row["cache_ratio"]
            if ratio is None:
                styled_row.append(Text("-"))
            else:
                ratio_str = f"{ratio:.1f}%"
                if ratio > 95:
                    styled_row.append(Text(ratio_str, style="on green"))
                else:
                    styled_row.append(ratio_str)
            table.add_row(*styled_row)

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
        notification_entries = [
            msg
            for msg in agent_message.notification_messages.values()
            if msg is not None
        ]

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
            recent_generations = token_manager.recent_generations
        else:
            recent_generations = None

        cleanable_messages = get_cleanable_large_messages(
            orchestration.large_messages,
            orchestration.agent_message,
            cleaned_messages_dict=orchestration.cleaned_messages,
        )
        can_clean, cleanable_count, cleanable_tokens = check_cleanable_threshold(
            cleanable_messages
        )

        notification_details = compute_notification_details(
            agent_message.notification_messages
        )

        system_prompt_tokens: int | None = None
        for msg in pinned_messages:
            if isinstance(msg, SystemMessage):
                system_prompt_tokens = estimate_message_tokens(msg)
                break

        stats = compute_context_statistics(
            messages=messages,
            pinned_messages=pinned_messages,
            notification_entries=notification_entries,
            notification_details=notification_details,
            large_message_count=len(orchestration.large_messages),
            cleanable_large_message_count=cleanable_count,
            cleanable_large_message_tokens=cleanable_tokens,
            can_clean_large_messages=can_clean,
            threshold_info=threshold_info,
            token_limit=token_limit,
            generation_count=generation_count,
            current_token_usage=current_token_usage,
            cumulative_token_usage=cumulative_token_usage,
            system_prompt_tokens=system_prompt_tokens,
            recent_generations=recent_generations,
        )

        self._update_cumulative_token_usage(stats)
        self._update_message_statistics(stats)
        self._update_pinned_message_statistics(stats)
        self._update_notification_message_statistics(stats)
        self._update_notification_details(stats)
        self._update_token_usage(stats)
        self._update_cache_status(stats)
        self._update_recent_cache_status(stats)
