"""测试Context tab功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.tui.app import TUIApp
from linhai.tui.context_tab import ContextTabWidget
from linhai.context_statistics import estimate_message_tokens
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.utils.i18n import t
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration


def _build_context_statistics(
    hard_limit=None,
    used_tokens=None,
    token_limit=None,
    generation_count=None,
    cache_info=None,
    cumulative_cache=None,
    cumulative_total_tokens=None,
    cumulative_input_tokens=None,
    cumulative_output_tokens=None,
    cumulative_cache_miss_count=None,
    system_prompt_tokens=None,
    large_message_count=0,
    cleanable_large_message_count=0,
    cleanable_large_message_tokens=0,
    can_clean_large_messages=False,
    messages_stats=None,
    pinned_stats=None,
    notification_stats=None,
    notification_details=None,
    recent_cache_rows=None,
    is_token_dirty=False,
):
    from linhai.context_statistics import (
        MessageGroupStatistics,
        MessageTypeCounts,
        ContextStatistics,
    )

    empty_stats: MessageGroupStatistics = {
        "count": 0,
        "sparkline": [],
        "type_counts": MessageTypeCounts(
            user=0,
            assistant=0,
            system=0,
            runtime=0,
            other=0,
        ),
        "total_tokens": 0,
        "avg_tokens": 0.0,
        "longest": None,
    }
    return ContextStatistics(
        messages=messages_stats or empty_stats,
        pinned_messages=pinned_stats or empty_stats,
        notification_messages=notification_stats or empty_stats,
        notification_details=(
            notification_details if notification_details is not None else []
        ),
        large_message_count=large_message_count,
        cleanable_large_message_count=cleanable_large_message_count,
        cleanable_large_message_tokens=cleanable_large_message_tokens,
        can_clean_large_messages=can_clean_large_messages,
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
        system_prompt_tokens=system_prompt_tokens,
        recent_cache_rows=recent_cache_rows,
        is_token_dirty=is_token_dirty,
    )


class TestContextTab(unittest.TestCase):
    """测试Context tab功能"""

    def test_context_tab_creation(self):
        """测试ContextTabWidget创建"""
        registry = Registry()
        widget = ContextTabWidget(registry)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.refresh_interval, 1.0)

    @patch("linhai.tui.context_tab.ContextTabWidget.update_display")
    @patch("linhai.tui.context_tab.ContextTabWidget.set_interval")
    def test_on_mount(self, mock_set_interval, mock_update_display):
        """测试组件挂载"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        widget.on_mount()

        mock_update_display.assert_called_once()
        mock_set_interval.assert_called_once_with(1.0, widget.update_display)

    @patch("linhai.tui.app.TUIApp.on_mount")
    def test_context_tab_in_app(self, mock_on_mount):
        """测试Context tab是否在应用中正确显示"""
        mock_on_mount.return_value = None

        registry = Registry()

        from linhai.agent.main import Agent

        mock_agent = Mock(spec=Agent)
        mock_agent_message = Mock(spec=AgentMessage)
        mock_orchestration = Mock(spec=AgentContextOrchestration)

        from linhai.base import UserMessage, AssistantMessage
        from linhai.agent.messages import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息"),
            AssistantMessage(message="测试助手消息"),
            RuntimeMessage("测试运行时消息"),
        ]
        mock_agent_message.messages = mock_messages
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = set()
        mock_orchestration.agent_message = mock_agent_message
        mock_orchestration.cleaned_messages = {}

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "remaining_tokens": 2000,
            "usage_ratio": 0.75,
        }

        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        import argparse

        mock_cli_args = argparse.Namespace(planning=False)
        registry.register_member("cli_args", mock_cli_args)
        from linhai.base import AnswerTokenUsage

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_agent.last_token_usage = mock_token_usage
        mock_agent.last_token_usage_object = None

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        from linhai.token_manager import TokenManager

        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.generation_count = 0
        mock_token_manager.recent_generations = []
        mock_token_manager.get_token_info = Mock(
            return_value=type(
                "TokenInfo",
                (),
                {
                    "is_dirty": False,
                    "current_token_usage": mock_token_usage,
                    "cumulative_token_usage": None,
                },
            )()
        )

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        from linhai.agent.lifecycle import Lifecycle

        Lifecycle(registry)
        with patch("linhai.tui.app.TokenManager", return_value=mock_token_manager):
            registry.register_member("token_manager", mock_token_manager)

            app = TUIApp(
                registry=registry,
                tui_config=TUIConfig(),
                init_messages=[],
                init_files=[],
            )

        async def _run_test():
            async with app.run_test() as pilot:
                tabbed_content = pilot.app.query_one("#main-tabs")
                self.assertIsNotNone(tabbed_content)

                agent_tab = pilot.app.query_one("#agent-tab")
                context_tab = pilot.app.query_one("#context-tab")

                self.assertIsNotNone(agent_tab)
                self.assertIsNotNone(context_tab)

                context_widgets = context_tab.query(ContextTabWidget)
                self.assertEqual(len(context_widgets), 1)

        asyncio.run(_run_test())

    def _create_mock_registry(self, registry: Registry, mock_agent: Mock) -> list:
        """Helper to set up mock registry members for update_display tests."""
        from linhai.base import AnswerTokenUsage
        from linhai.token_manager import TokenManager

        mock_agent_message = Mock(spec=AgentMessage)
        mock_orchestration = Mock(spec=AgentContextOrchestration)

        from linhai.base import UserMessage, AssistantMessage
        from linhai.agent.messages import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息"),
            AssistantMessage(message="测试助手消息"),
            RuntimeMessage("测试运行时消息"),
        ]
        mock_agent_message.messages = mock_messages
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = set()
        mock_orchestration.agent_message = mock_agent_message
        mock_orchestration.cleaned_messages = {}

        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "remaining_tokens": 2000,
            "usage_ratio": 0.75,
        }

        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.generation_count = 0
        mock_token_manager.recent_generations = []
        mock_token_manager.get_token_info = Mock(
            return_value=type(
                "TokenInfo",
                (),
                {
                    "is_dirty": False,
                    "current_token_usage": mock_token_usage,
                    "cumulative_token_usage": None,
                },
            )()
        )

        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        registry.register_member("agent", mock_agent)
        registry.register_member("token_manager", mock_token_manager)

        return mock_messages

    def test_update_display_with_mocks(self):
        """测试update_display功能"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        from linhai.agent.main import Agent

        mock_agent = Mock(spec=Agent)
        mock_messages = self._create_mock_registry(registry, mock_agent)

        from textual.widgets import ProgressBar, Sparkline, Static, DataTable

        mock_cumulative_stats_text = Mock(spec=Static)
        mock_sparkline = Mock(spec=Sparkline)
        mock_stats_text = Mock(spec=Static)
        mock_pinned_sparkline = Mock(spec=Sparkline)
        mock_pinned_text = Mock(spec=Static)
        mock_notif_text = Mock(spec=Static)
        mock_notif_list_text = Mock(spec=Static)
        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)
        mock_pb_cache = Mock(spec=ProgressBar)
        mock_cache_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, _expect_type=None, **_kwargs):
            mapping = {
                "#cumulative-token-stats-text": mock_cumulative_stats_text,
                "#msg-stats-sparkline": mock_sparkline,
                "#msg-stats-text": mock_stats_text,
                "#pinned-stats-sparkline": mock_pinned_sparkline,
                "#pinned-stats-text": mock_pinned_text,
                "#notification-stats-text": mock_notif_text,
                "#notification-list-text": mock_notif_list_text,
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
                "#pb-cache-ratio": mock_pb_cache,
                "#cache-stats-text": mock_cache_stats_text,
                "#recent-cache-table": Mock(spec=DataTable),
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget.update_display()

        from math import log2

        expected_data = [
            float(log2(estimate_message_tokens(msg) + 1)) for msg in mock_messages
        ]
        self.assertEqual(mock_sparkline.data, expected_data)
        mock_stats_text.update.assert_called_once()
        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=6000.0)
        mock_pb_model.update.assert_called_once_with(total=128000.0, progress=6000.0)
        mock_token_stats_text.update.assert_called_once()

        stats_call_args = mock_stats_text.update.call_args[0][0]
        self.assertIn(
            f"{t({'zh_CN': '总消息数', 'en': 'Total messages'})}: 3", stats_call_args
        )
        self.assertIn(t({"zh_CN": "平均长度", "en": "Average length"}), stats_call_args)
        self.assertNotIn("消息平均Token数", stats_call_args)
        self.assertIn(
            t({"zh_CN": "最长消息", "en": "Longest message"}), stats_call_args
        )
        self.assertIn(
            f"{t({'zh_CN': '大消息数量', 'en': 'Large messages'})}: 0", stats_call_args
        )
        self.assertIn(
            f"{t({'zh_CN': '可清理大消息', 'en': 'Cleanable large messages'})}: 0",
            stats_call_args,
        )
        self.assertIn(
            f"{t({'zh_CN': '可清理大消息token量', 'en': 'Cleanable large messages tokens'})}: 0",
            stats_call_args,
        )
        self.assertIn(
            f"{t({'zh_CN': '是否可清理', 'en': 'Can clean'})}: {t({'zh_CN': '否', 'en': 'No'})}",
            stats_call_args,
        )

        token_stats_args = mock_token_stats_text.update.call_args[0][0]
        self.assertIn(
            f"{t({'zh_CN': '当前用量', 'en': 'Current usage'})}: 6000", token_stats_args
        )
        self.assertIn(
            f"{t({'zh_CN': 'Token限制', 'en': 'Token limit'})}: 128000",
            token_stats_args,
        )
        self.assertIn(
            f"{t({'zh_CN': '当前消息缓存状态', 'en': 'Current message cache status'})}（{t({'zh_CN': '实际', 'en': 'actual'})}）",
            token_stats_args,
        )
        self.assertNotIn("当前消息估算缓存Token数", token_stats_args)

    def test_update_token_usage_no_threshold(self):
        """测试threshold_info不可用时的token用量显示"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, _expect_type=None, **_kwargs):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        stats = _build_context_statistics()
        widget._update_token_usage(stats)

        mock_token_stats_text.update.assert_called_once_with(
            t({"zh_CN": "不可用", "en": "N/A"})
        )

    def test_update_token_usage_with_no_cache(self):
        """测试无缓存时的token用量显示"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, _expect_type=None, **_kwargs):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        from linhai.context_statistics import CacheInfo

        cache_info = CacheInfo(cached_tokens=0, percentage=0.0, is_estimated=True)
        stats = _build_context_statistics(
            hard_limit=8000,
            used_tokens=3000,
            token_limit=128000,
            generation_count=0,
            cache_info=cache_info,
        )
        widget._update_token_usage(stats)

        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=3000.0)
        mock_pb_model.update.assert_called_once_with(total=128000.0, progress=3000.0)

        token_stats_args = mock_token_stats_text.update.call_args[0][0]
        self.assertIn(
            f"{t({'zh_CN': '当前用量', 'en': 'Current usage'})}: 3000", token_stats_args
        )
        self.assertIn(
            f"{t({'zh_CN': 'Token限制', 'en': 'Token limit'})}: 128000",
            token_stats_args,
        )
        self.assertNotIn("缓存比例", token_stats_args)

    def test_update_token_usage_no_token_limit(self):
        """测试token_limit为None时的回退行为"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, _expect_type=None, **_kwargs):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        from linhai.context_statistics import CacheInfo

        cache_info = CacheInfo(cached_tokens=0, percentage=0.0, is_estimated=True)
        stats = _build_context_statistics(
            hard_limit=8000,
            used_tokens=5000,
            token_limit=None,
            generation_count=0,
            cache_info=cache_info,
        )
        widget._update_token_usage(stats)

        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=5000.0)
        mock_pb_model.update.assert_called_once_with(total=100.0, progress=100.0)

    def test_compute_recent_cache_rows_types(self):
        from linhai.context_statistics import compute_recent_cache_rows
        from linhai.base import AnswerTokenUsage

        usage = AnswerTokenUsage(
            input_tokens=500,
            output_tokens=100,
            total_tokens=600,
            cached_input_tokens=400,
            estimated_cached_input_tokens=350,
        )
        rows = compute_recent_cache_rows([usage])
        self.assertIsNotNone(rows)
        row = rows[0]
        self.assertIsInstance(row["input_tokens"], int)
        self.assertIsInstance(row["actual_cached_tokens"], int)
        self.assertIsInstance(row["estimated_cached_tokens"], int)
        self.assertIsInstance(row["non_cached_tokens"], int)
        self.assertIsInstance(row["output_tokens"], int)
        self.assertIsInstance(row["cache_ratio"], float)
        self.assertEqual(row["input_tokens"], 500)
        self.assertEqual(row["actual_cached_tokens"], 400)
        self.assertEqual(row["non_cached_tokens"], 100)

    def test_compute_recent_cache_rows_none_values(self):
        from linhai.context_statistics import compute_recent_cache_rows
        from linhai.base import AnswerTokenUsage

        usage = AnswerTokenUsage(
            input_tokens=500,
            output_tokens=100,
            total_tokens=600,
            cached_input_tokens=None,
            estimated_cached_input_tokens=None,
        )
        rows = compute_recent_cache_rows([usage])
        self.assertIsNotNone(rows)
        row = rows[0]
        self.assertIsNone(row["actual_cached_tokens"])
        self.assertIsNone(row["estimated_cached_tokens"])
        self.assertIsNone(row["non_cached_tokens"])
        self.assertIsNone(row["cache_ratio"])

    def test_recent_cache_table_styling(self):
        from textual.widgets import DataTable
        from rich.text import Text
        from linhai.context_statistics import RecentGenerationCacheRow

        registry = Registry()
        widget = ContextTabWidget(registry)

        mock_table = Mock(spec=DataTable)
        mock_table.columns = []

        widget.query_one = Mock(return_value=mock_table)

        rows = [
            RecentGenerationCacheRow(
                input_tokens=500,
                actual_cached_tokens=400,
                estimated_cached_tokens=350,
                non_cached_tokens=100,
                output_tokens=50,
                cache_ratio=80.0,
            ),
            RecentGenerationCacheRow(
                input_tokens=2000,
                actual_cached_tokens=1900,
                estimated_cached_tokens=1850,
                non_cached_tokens=100,
                output_tokens=200,
                cache_ratio=96.0,
            ),
        ]

        stats = _build_context_statistics(recent_cache_rows=rows)
        widget._update_recent_cache_status(stats)

        self.assertTrue(mock_table.add_row.called)
        self.assertEqual(mock_table.add_row.call_count, 2)

        call_args = mock_table.add_row.call_args_list[0][0]
        self.assertIsInstance(call_args[0], Text)
        self.assertIn("grey50", str(call_args[0].style))
        self.assertEqual(call_args[0].plain, "500")

        call_args2 = mock_table.add_row.call_args_list[1][0]
        self.assertIsInstance(call_args2[5], Text)
        self.assertIn("on darkgreen", str(call_args2[5].style))
        self.assertIn("96.0%", call_args2[5].plain)


class TestPinnedAndNotificationStats(unittest.TestCase):
    """测试置顶消息和通知消息统计功能"""

    def _create_widget_with_mocks(
        self, pinned_messages=None, notification_messages=None
    ):
        from textual.widgets import Sparkline, Static, ProgressBar, DataTable
        from linhai.agent.main import Agent
        from linhai.base import AnswerTokenUsage, UserMessage, AssistantMessage
        from linhai.token_manager import TokenManager

        registry = Registry()
        widget = ContextTabWidget(registry)

        mock_agent = Mock(spec=Agent)
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "remaining_tokens": 2000,
            "usage_ratio": 0.75,
        }
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        mock_agent_message = Mock(spec=AgentMessage)
        mock_agent_message.messages = [
            UserMessage(message="用户消息"),
            AssistantMessage(message="助手消息"),
        ]
        mock_agent_message.pinned_messages = (
            pinned_messages if pinned_messages is not None else []
        )
        mock_agent_message.notification_messages = (
            notification_messages if notification_messages is not None else {}
        )

        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = set()
        mock_orchestration.agent_message = mock_agent_message
        mock_orchestration.cleaned_messages = {}

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.generation_count = 0
        mock_token_manager.recent_generations = []
        mock_token_manager.get_token_info = Mock(
            return_value=type(
                "TokenInfo",
                (),
                {
                    "is_dirty": False,
                    "current_token_usage": mock_token_usage,
                    "cumulative_token_usage": None,
                },
            )()
        )

        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        registry.register_member("agent", mock_agent)
        registry.register_member("token_manager", mock_token_manager)

        mock_cumulative_stats_text = Mock(spec=Static)
        mock_sparkline = Mock(spec=Sparkline)
        mock_stats_text = Mock(spec=Static)
        mock_pinned_sparkline = Mock(spec=Sparkline)
        mock_pinned_text = Mock(spec=Static)
        mock_notif_text = Mock(spec=Static)
        mock_notif_list_text = Mock(spec=Static)
        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)
        mock_pb_cache = Mock(spec=ProgressBar)
        mock_cache_stats_text = Mock(spec=Static)

        mock_query_map = {
            "#cumulative-token-stats-text": mock_cumulative_stats_text,
            "#msg-stats-sparkline": mock_sparkline,
            "#msg-stats-text": mock_stats_text,
            "#pinned-stats-sparkline": mock_pinned_sparkline,
            "#pinned-stats-text": mock_pinned_text,
            "#notification-stats-text": mock_notif_text,
            "#notification-list-text": mock_notif_list_text,
            "#pb-hard-limit": mock_pb_hard,
            "#pb-model-limit": mock_pb_model,
            "#token-stats-text": mock_token_stats_text,
            "#pb-cache-ratio": mock_pb_cache,
            "#cache-stats-text": mock_cache_stats_text,
            "#recent-cache-table": Mock(spec=DataTable),
        }

        widget.query_one = Mock(
            side_effect=lambda sel, tp=None, **kw: mock_query_map[sel]
        )

        return (
            widget,
            mock_pinned_sparkline,
            mock_pinned_text,
            mock_notif_text,
            mock_notif_list_text,
        )

    def test_pinned_empty(self):
        widget, _, mock_pinned_text, _, _ = self._create_widget_with_mocks()
        widget.update_display()
        mock_pinned_text.update.assert_called_with(
            t({"zh_CN": "无置顶消息", "en": "No pinned messages"})
        )

    def test_notification_empty(self):
        widget, _, _, mock_notif_text, mock_notif_list_text = (
            self._create_widget_with_mocks()
        )
        widget.update_display()
        mock_notif_text.update.assert_called_with(
            t({"zh_CN": "无通知消息", "en": "No notification messages"})
        )
        mock_notif_list_text.update.assert_called_with(
            t({"zh_CN": "无通知消息", "en": "No notification messages"})
        )

    def test_pinned_with_messages(self):
        from linhai.base import UserMessage
        from math import log2

        pinned = [UserMessage(message="系统指令1"), UserMessage(message="系统指令2")]
        widget, mock_pinned_sparkline, mock_pinned_text, _, _ = (
            self._create_widget_with_mocks(pinned_messages=pinned)
        )
        widget.update_display()

        expected_data = [
            float(log2(estimate_message_tokens(msg) + 1)) for msg in pinned
        ]
        self.assertEqual(mock_pinned_sparkline.data, expected_data)

        text_arg = mock_pinned_text.update.call_args[0][0]
        self.assertIn(
            f"{t({'zh_CN': '总消息数', 'en': 'Total messages'})}: 2", text_arg
        )
        self.assertIn(t({"zh_CN": "平均长度", "en": "Average length"}), text_arg)
        self.assertNotIn("消息平均Token数", text_arg)
        self.assertNotIn(t({"zh_CN": "最长消息", "en": "Longest message"}), text_arg)
        self.assertNotIn("大消息", text_arg)
        self.assertNotIn("System Prompt", text_arg)

    def test_pinned_with_system_message(self):
        from linhai.base import SystemMessage, UserMessage
        from unittest.mock import MagicMock

        registry = Registry()
        mock_system = MagicMock(spec=SystemMessage)
        mock_system.get_content.return_value = "test system prompt content"
        pinned = [mock_system, UserMessage(message="用户指令")]
        widget, _, mock_pinned_text, _, _ = self._create_widget_with_mocks(
            pinned_messages=pinned
        )
        widget.update_display()

        text_arg = mock_pinned_text.update.call_args[0][0]
        self.assertIn("System Prompt", text_arg)
        self.assertIn("token", text_arg)

    def test_notification_with_messages(self):
        from linhai.base import UserMessage

        msg1 = UserMessage(message="通知1")
        msg2 = UserMessage(message="通知2")
        notifications = {
            "a": msg1,
            "b": msg2,
        }
        widget, _, _, mock_notif_text, _ = self._create_widget_with_mocks(
            notification_messages=notifications
        )
        widget.update_display()

        text_arg = mock_notif_text.update.call_args[0][0]
        self.assertIn(
            f"{t({'zh_CN': '总消息数', 'en': 'Total messages'})}: 2", text_arg
        )
        self.assertIn(t({"zh_CN": "平均长度", "en": "Average length"}), text_arg)
        self.assertNotIn("消息平均Token数", text_arg)
        self.assertIn(t({"zh_CN": "最长消息", "en": "Longest message"}), text_arg)

    def test_notification_details_display(self):
        from linhai.base import UserMessage
        from linhai.agent.messages import RuntimeMessage

        msg1 = RuntimeMessage("runtime内容")
        msg2 = UserMessage(message="通知内容")
        notifications = {
            "a": msg1,
            "b": msg2,
        }
        widget, _, _, _, mock_notif_list_text = self._create_widget_with_mocks(
            notification_messages=notifications
        )
        widget.update_display()

        text_arg = mock_notif_list_text.update.call_args[0][0]
        self.assertIn("[a]", text_arg)
        self.assertIn("runtime内容", text_arg)
        self.assertNotIn("<<runtime>>", text_arg)
        self.assertIn("[b]", text_arg)
        self.assertIn("通知内容", text_arg)

    def test_notification_details_truncation(self):
        from linhai.base import UserMessage

        long_content = "你好" * 200
        msg = UserMessage(message=long_content)
        notifications = {
            "a": msg,
        }
        widget, _, _, _, mock_notif_list_text = self._create_widget_with_mocks(
            notification_messages=notifications
        )
        widget.update_display()

        text_arg = mock_notif_list_text.update.call_args[0][0]
        self.assertIn("...", text_arg)
        self.assertNotIn(long_content, text_arg)


class TestFindLongestMessageWithOpenAiToolResult(unittest.TestCase):
    """测试 _find_longest_message 正确处理 OpenAiToolResultMessage"""

    def test_openai_tool_result_tool_name_displayed(self):
        from linhai.context_statistics import compute_message_group_stats
        from linhai.base import OpenAiToolResultMessage, UserMessage

        msgs = [
            UserMessage(message="短消息"),
            OpenAiToolResultMessage(
                tool_call_id="call_123",
                content="这是" + "工具" * 50 + "结果",
                tool_name="test_tool",
            ),
        ]
        stats = compute_message_group_stats(msgs)
        longest = stats["longest"]
        self.assertIsNotNone(longest)
        self.assertEqual(longest["type_name"], "OpenAiToolResultMessage")
        self.assertEqual(longest["tool_name"], "test_tool")

    def test_openai_tool_result_tool_name_none(self):
        from linhai.context_statistics import compute_message_group_stats
        from linhai.base import OpenAiToolResultMessage, UserMessage

        msgs = [
            UserMessage(message="短消息"),
            OpenAiToolResultMessage(
                tool_call_id="call_456",
                content="这是" + "工具" * 50 + "结果",
                tool_name="test_tool",
            ),
        ]
        stats = compute_message_group_stats(msgs)
        longest = stats["longest"]
        self.assertIsNotNone(longest)
        self.assertEqual(longest["type_name"], "OpenAiToolResultMessage")
        self.assertEqual(longest["tool_name"], "test_tool")

    def test_format_longest_message_with_tool_name(self):
        from linhai.context_statistics import LongestMessageInfo
        from linhai.tui.context_tab import _format_longest_message

        info = LongestMessageInfo(
            type_name="OpenAiToolResultMessage",
            tool_name="test_tool",
            tokens=5000,
        )
        result = _format_longest_message(info)
        self.assertIn("OpenAiToolResultMessage", result)
        self.assertIn("test_tool", result)
        self.assertIn("5000", result)

    def test_format_longest_message_without_tool_name(self):
        from linhai.context_statistics import LongestMessageInfo
        from linhai.tui.context_tab import _format_longest_message

        info = LongestMessageInfo(
            type_name="OpenAiToolResultMessage",
            tool_name="",
            tokens=5000,
        )
        result = _format_longest_message(info)
        self.assertIn("OpenAiToolResultMessage", result)
        self.assertIn("5000", result)


if __name__ == "__main__":
    unittest.main()
