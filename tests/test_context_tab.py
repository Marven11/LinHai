"""测试Context tab功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.tui.app import TUIApp
from linhai.tui.context_tab import ContextTabWidget
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration


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

        from linhai.llm import UserMessage, AssistantMessage
        from linhai.agent.base import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息"),
            AssistantMessage(message="测试助手消息"),
            RuntimeMessage("测试运行时消息"),
        ]
        mock_agent_message.messages = mock_messages
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = {}

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
        from linhai.llm import AnswerTokenUsage

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

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        registry.register_member("lifecycle", mock_lifecycle)
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
        from linhai.llm import AnswerTokenUsage
        from linhai.token_manager import TokenManager
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration

        mock_agent_message = Mock(spec=AgentMessage)
        mock_orchestration = Mock(spec=AgentContextOrchestration)

        from linhai.llm import UserMessage, AssistantMessage
        from linhai.agent.base import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息"),
            AssistantMessage(message="测试助手消息"),
            RuntimeMessage("测试运行时消息"),
        ]
        mock_agent_message.messages = mock_messages
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = {}

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

        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        registry.register_member("agent", mock_agent)
        registry.register_member("token_manager", mock_token_manager)

        return mock_messages

    def test_update_display_with_mocks(self):
        """测试update_display功能"""
        from unittest.mock import MagicMock

        registry = Registry()
        widget = ContextTabWidget(registry)

        from linhai.agent.main import Agent

        mock_agent = Mock(spec=Agent)
        mock_messages = self._create_mock_registry(registry, mock_agent)

        from textual.widgets import ProgressBar, Sparkline, Static

        mock_cumulative_stats_text = Mock(spec=Static)
        mock_sparkline = Mock(spec=Sparkline)
        mock_stats_text = Mock(spec=Static)
        mock_pinned_sparkline = Mock(spec=Sparkline)
        mock_pinned_text = Mock(spec=Static)
        mock_notif_text = Mock(spec=Static)
        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)
        mock_pb_cache = Mock(spec=ProgressBar)
        mock_cache_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, expect_type=None):
            mapping = {
                "#cumulative-token-stats-text": mock_cumulative_stats_text,
                "#msg-stats-sparkline": mock_sparkline,
                "#msg-stats-text": mock_stats_text,
                "#pinned-stats-sparkline": mock_pinned_sparkline,
                "#pinned-stats-text": mock_pinned_text,
                "#notification-stats-text": mock_notif_text,
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
                "#pb-cache-ratio": mock_pb_cache,
                "#cache-stats-text": mock_cache_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget.update_display()

        from math import log2

        expected_data = [
            float(log2(widget._estimate_message_tokens(msg))) for msg in mock_messages
        ]
        self.assertEqual(mock_sparkline.data, expected_data)
        mock_stats_text.update.assert_called_once()
        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=6000.0)
        mock_pb_model.update.assert_called_once_with(total=128000.0, progress=6000.0)
        mock_token_stats_text.update.assert_called_once()

        stats_call_args = mock_stats_text.update.call_args[0][0]
        self.assertIn("总消息数: 3", stats_call_args)
        self.assertIn("平均长度", stats_call_args)
        self.assertNotIn("消息平均Token数", stats_call_args)
        self.assertIn("最长消息", stats_call_args)
        self.assertIn("大消息数量: 0", stats_call_args)

        token_stats_args = mock_token_stats_text.update.call_args[0][0]
        self.assertIn("当前用量: 6000", token_stats_args)
        self.assertIn("Token限制: 128000", token_stats_args)
        self.assertIn("当前消息缓存状态（估算）", token_stats_args)
        self.assertNotIn("当前消息估算缓存Token数", token_stats_args)

    def test_update_token_usage_no_agent(self):
        """测试Agent未初始化时的token用量显示"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, expect_type=None):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget._update_token_usage(None)

        mock_token_stats_text.update.assert_called_once_with("Agent未初始化")

    def test_update_token_usage_no_threshold(self):
        """测试threshold_info不可用时的token用量显示"""
        from linhai.agent.main import Agent

        registry = Registry()
        mock_agent = Mock(spec=Agent)
        mock_agent.get_threshold_info.return_value = None

        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, expect_type=None):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget._update_token_usage(mock_agent)

        mock_token_stats_text.update.assert_called_once_with("不可用")

    def test_update_token_usage_with_no_cache(self):
        """测试无缓存时的token用量显示"""
        from linhai.agent.main import Agent
        from linhai.llm import AnswerTokenUsage
        from linhai.token_manager import TokenManager

        registry = Registry()
        mock_agent = Mock(spec=Agent)
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 3000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.375,
        }
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        mock_token_usage = AnswerTokenUsage(
            input_tokens=3000,
            output_tokens=0,
            total_tokens=3000,
            cached_input_tokens=None,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        registry.register_member("token_manager", mock_token_manager)

        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, expect_type=None):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget._update_token_usage(mock_agent)

        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=3000.0)
        mock_pb_model.update.assert_called_once_with(total=128000.0, progress=3000.0)

        token_stats_args = mock_token_stats_text.update.call_args[0][0]
        self.assertIn("当前用量: 3000", token_stats_args)
        self.assertIn("Token限制: 128000", token_stats_args)
        self.assertNotIn("缓存比例", token_stats_args)

    def test_update_token_usage_no_token_limit(self):
        """测试token_limit为None时的回退行为"""
        from linhai.agent.main import Agent
        from linhai.llm import AnswerTokenUsage
        from linhai.token_manager import TokenManager

        registry = Registry()
        mock_agent = Mock(spec=Agent)
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 5000,
            "remaining_tokens": 3000,
            "usage_ratio": 0.625,
        }
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = None
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        mock_token_usage = AnswerTokenUsage(
            input_tokens=5000,
            output_tokens=0,
            total_tokens=5000,
            cached_input_tokens=None,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        registry.register_member("token_manager", mock_token_manager)

        widget = ContextTabWidget(registry)

        from textual.widgets import ProgressBar, Static

        mock_pb_hard = Mock(spec=ProgressBar)
        mock_pb_model = Mock(spec=ProgressBar)
        mock_token_stats_text = Mock(spec=Static)

        def _mock_query_one(selector, expect_type=None):
            mapping = {
                "#pb-hard-limit": mock_pb_hard,
                "#pb-model-limit": mock_pb_model,
                "#token-stats-text": mock_token_stats_text,
            }
            return mapping[selector]

        widget.query_one = Mock(side_effect=_mock_query_one)

        widget._update_token_usage(mock_agent)

        mock_pb_hard.update.assert_called_once_with(total=8000.0, progress=5000.0)
        mock_pb_model.update.assert_called_once_with(total=100.0, progress=100.0)


class TestPinnedAndNotificationStats(unittest.TestCase):
    """测试置顶消息和通知消息统计功能"""

    def _create_widget_with_mocks(
        self, pinned_messages=None, notification_messages=None
    ):
        from textual.widgets import Sparkline, Static, ProgressBar
        from linhai.agent.main import Agent
        from linhai.llm import AnswerTokenUsage, UserMessage, AssistantMessage
        from linhai.token_manager import TokenManager
        from linhai.agent.message import AgentMessage, NotificationMessageEntry
        from linhai.agent.orchestration import AgentContextOrchestration

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
        mock_orchestration.large_messages = {}

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage
        mock_token_manager.cumulative_token_usage = None

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
            "#pb-hard-limit": mock_pb_hard,
            "#pb-model-limit": mock_pb_model,
            "#token-stats-text": mock_token_stats_text,
            "#pb-cache-ratio": mock_pb_cache,
            "#cache-stats-text": mock_cache_stats_text,
        }

        widget.query_one = Mock(
            side_effect=lambda sel, tp=None, **kw: mock_query_map[sel]
        )

        return (
            widget,
            mock_pinned_sparkline,
            mock_pinned_text,
            mock_notif_text,
        )

    def test_pinned_empty(self):
        widget, _, mock_pinned_text, _ = self._create_widget_with_mocks()
        widget.update_display()
        mock_pinned_text.update.assert_called_with("无置顶消息")

    def test_notification_empty(self):
        widget, _, _, mock_notif_text = self._create_widget_with_mocks()
        widget.update_display()
        mock_notif_text.update.assert_called_with("无通知消息")

    def test_pinned_with_messages(self):
        from linhai.llm import UserMessage
        from math import log2

        pinned = [UserMessage(message="系统指令1"), UserMessage(message="系统指令2")]
        widget, mock_pinned_sparkline, mock_pinned_text, _ = (
            self._create_widget_with_mocks(pinned_messages=pinned)
        )
        widget.update_display()

        expected_data = [
            float(log2(widget._estimate_message_tokens(msg))) for msg in pinned
        ]
        self.assertEqual(mock_pinned_sparkline.data, expected_data)

        text_arg = mock_pinned_text.update.call_args[0][0]
        self.assertIn("总消息数: 2", text_arg)
        self.assertIn("平均长度", text_arg)
        self.assertNotIn("消息平均Token数", text_arg)
        self.assertNotIn("最长消息", text_arg)
        self.assertNotIn("大消息", text_arg)

    def test_notification_with_messages(self):
        from linhai.llm import UserMessage
        from linhai.agent.message import NotificationMessageEntry

        msg1 = UserMessage(message="通知1")
        msg2 = UserMessage(message="通知2")
        notifications = {
            "a": NotificationMessageEntry(source="a", message=msg1, sort_value=1),
            "b": NotificationMessageEntry(source="b", message=msg2, sort_value=2),
        }
        widget, _, _, mock_notif_text = self._create_widget_with_mocks(
            notification_messages=notifications
        )
        widget.update_display()

        text_arg = mock_notif_text.update.call_args[0][0]
        self.assertIn("总消息数: 2", text_arg)
        self.assertIn("平均长度", text_arg)
        self.assertNotIn("消息平均Token数", text_arg)
        self.assertIn("最长消息", text_arg)


if __name__ == "__main__":
    unittest.main()
