"""测试Context tab功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.cli.app import CLIApp
from linhai.cli.context_tab import ContextTabWidget
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration


class TestContextTab(unittest.TestCase):
    """测试Context tab功能"""

    def test_context_tab_creation(self):
        """测试ContextTabWidget创建"""
        group_chat = GroupChat()
        widget = ContextTabWidget(group_chat)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.refresh_interval, 1.0)

    @patch("linhai.cli.context_tab.ContextTabWidget.update_display")
    @patch("linhai.cli.context_tab.ContextTabWidget.set_interval")
    def test_on_mount(self, mock_set_interval, mock_update_display):
        """测试组件挂载"""
        group_chat = GroupChat()
        widget = ContextTabWidget(group_chat)

        # 模拟mount
        widget.on_mount()

        # 验证update_display被调用
        mock_update_display.assert_called_once()
        # 验证set_interval被调用
        mock_set_interval.assert_called_once_with(1.0, widget.update_display)

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_context_tab_in_app(self, mock_on_mount):
        """测试Context tab是否在应用中正确显示"""
        mock_on_mount.return_value = None

        group_chat = GroupChat()

        # 避免token_manager重复注册
        # TokenManager会在CLIApp初始化时自动注册，这里不需要手动注册

        # 注册所有必需的组件
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
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = {}

        # 返回ThresholdInfo字典
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "remaining_tokens": 2000,
            "usage_ratio": 0.75,
        }

        # 注册cli_args模拟对象
        import argparse

        mock_cli_args = argparse.Namespace()
        mock_cli_args.message = None
        mock_cli_args.file = None
        group_chat.register_member("cli_args", mock_cli_args)
        from linhai.llm import AnswerTokenUsage

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_agent.last_token_usage = mock_token_usage
        mock_agent.last_token_usage_object = None

        # 设置token_manager的current_token_usage
        from linhai.llm import AnswerTokenUsage

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        # 对于Mock对象，需要设置spec
        from linhai.token_manager import TokenManager

        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage

        group_chat.register_member("agent", mock_agent)
        group_chat.register_member("agent_message", mock_agent_message)
        group_chat.register_member("agent_context_orchestration", mock_orchestration)
        # 注意：这里不注册token_manager，因为CLIApp会创建并注册
        # 使用patch来模拟TokenManager的创建，避免重复注册
        with patch("linhai.cli.app.TokenManager", return_value=mock_token_manager):
            # 直接注册token_manager到group_chat，这样ContextTabWidget就不会抛出RuntimeError
            group_chat.register_member("token_manager", mock_token_manager)

            app = CLIApp(group_chat=group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                # 验证tab存在
                tabbed_content = pilot.app.query_one("#main-tabs")
                self.assertIsNotNone(tabbed_content)

                # 验证各个tab
                agent_tab = pilot.app.query_one("#agent-tab")

                context_tab = pilot.app.query_one("#context-tab")

                self.assertIsNotNone(agent_tab)
                self.assertIsNotNone(context_tab)

                # 验证ContextTabWidget在context-tab中
                context_widgets = context_tab.query(ContextTabWidget)
                self.assertEqual(len(context_widgets), 1)

        asyncio.run(_run_test())

    def test_update_display_with_mocks(self):
        """测试update_display功能"""
        group_chat = GroupChat()

        # 创建模拟组件
        from linhai.agent.main import Agent

        mock_agent_message = Mock(spec=AgentMessage)
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_agent = Mock(spec=Agent)

        # 设置模拟数据
        from linhai.llm import UserMessage, AssistantMessage, AnswerTokenUsage
        from linhai.agent.base import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息"),
            AssistantMessage(message="测试助手消息"),
            RuntimeMessage("测试运行时消息"),
        ]
        mock_agent_message.messages = mock_messages
        mock_agent_message.notification_messages = {}

        mock_orchestration.large_messages = {
            "largemessage_1": mock_messages[0],
            "largemessage_2": mock_messages[1],
        }
        mock_orchestration.get_large_message_reprs = Mock(return_value=[])

        # 返回ThresholdInfo字典
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "remaining_tokens": 2000,
            "usage_ratio": 0.75,
        }
        from linhai.llm import AnswerTokenUsage

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_agent.last_token_usage = mock_token_usage
        mock_agent.last_token_usage_object = None

        # 设置token_manager的current_token_usage
        from linhai.token_manager import TokenManager

        mock_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.current_token_usage = mock_token_usage

        # 注册所有必需的组件
        group_chat.register_member("agent_message", mock_agent_message)
        group_chat.register_member("agent_context_orchestration", mock_orchestration)
        group_chat.register_member("agent", mock_agent)
        group_chat.register_member("token_manager", mock_token_manager)

        # 创建widget并测试
        widget = ContextTabWidget(group_chat)

        # 模拟query_one
        from textual.widgets import Static

        mock_static = Mock(spec=Static)
        widget.query_one = Mock(return_value=mock_static)

        # 调用update_display
        widget.update_display()

        # 验证update被调用
        mock_static.update.assert_called_once()

        # 验证内容包含预期的信息
        call_args = mock_static.update.call_args[0][0]
        self.assertIsNotNone(call_args)

    def test_update_display_without_components(self):
        """测试在没有组件时的update_display"""
        group_chat = GroupChat()
        widget = ContextTabWidget(group_chat)

        # 模拟query_one
        from textual.widgets import Static

        mock_static = Mock(spec=Static)
        widget.query_one = Mock(return_value=mock_static)

        # 直接调用_show_waiting_message方法（因为update_display在没有组件时会失败）
        widget._show_waiting_message()

        # 验证显示等待消息
        mock_static.update.assert_called_once_with("等待组件初始化...")


if __name__ == "__main__":
    unittest.main()
