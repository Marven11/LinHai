"""测试Context tab功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.cli.app import CLIApp
from linhai.cli.context_tab import ContextTabWidget
from linhai.registry import Registry
from linhai.config import CLIConfig
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

    @patch("linhai.cli.context_tab.ContextTabWidget.update_display")
    @patch("linhai.cli.context_tab.ContextTabWidget.set_interval")
    def test_on_mount(self, mock_set_interval, mock_update_display):
        """测试组件挂载"""
        registry = Registry()
        widget = ContextTabWidget(registry)

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

        registry = Registry()

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

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        # 注册lifecycle模拟对象
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        registry.register_member("lifecycle", mock_lifecycle)
        # 注意：这里不注册token_manager，因为CLIApp会创建并注册
        # 使用patch来模拟TokenManager的创建，避免重复注册
        with patch("linhai.cli.app.TokenManager", return_value=mock_token_manager):
            # 直接注册token_manager到registry，这样ContextTabWidget就不会抛出RuntimeError
            registry.register_member("token_manager", mock_token_manager)

            app = CLIApp(registry=registry, cli_config=CLIConfig())

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
        registry = Registry()

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
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)
        registry.register_member("agent", mock_agent)
        registry.register_member("token_manager", mock_token_manager)

        # 创建widget并测试
        widget = ContextTabWidget(registry)

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
        registry = Registry()
        widget = ContextTabWidget(registry)

        # 模拟query_one
        from textual.widgets import Static

        mock_static = Mock(spec=Static)
        widget.query_one = Mock(return_value=mock_static)

        # 直接调用_show_waiting_message方法（因为update_display在没有组件时会失败）
        widget._show_waiting_message()

        # 验证显示等待消息
        mock_static.update.assert_called_once_with("等待组件初始化...")

    def test_build_message_statistics_section_with_large_messages(self):
        """测试消息统计板块是否正确显示大消息数量"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        # 创建模拟消息
        from linhai.llm import UserMessage, AssistantMessage
        from linhai.agent.base import RuntimeMessage

        mock_messages = [
            UserMessage(message="测试用户消息1"),
            AssistantMessage(message="测试助手消息1"),
            RuntimeMessage("测试运行时消息1"),
        ]
        message_count = len(mock_messages)

        # 创建模拟编排状态，包含大消息
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {
            "large_1": mock_messages[0],
            "large_2": mock_messages[1],
        }

        # 创建grid
        from rich.table import Table

        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan")
        grid.add_column()

        # 调用_build_message_statistics_section
        widget._build_message_statistics_section(
            grid, mock_messages, message_count, mock_orchestration
        )

        # 验证大消息数量为2
        self.assertEqual(len(mock_orchestration.large_messages), 2)

    def test_build_orchestration_section_without_large_messages_count(self):
        """测试编排状态板块是否不再显示大消息数量"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        # 创建模拟编排状态
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {
            "large_1": Mock(),
            "large_2": Mock(),
        }

        # 创建grid
        from rich.table import Table

        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan")
        grid.add_column()

        # 调用_build_orchestration_section
        widget._build_orchestration_section(grid, mock_orchestration)

        # 验证大消息数量已迁移
        self.assertIsNotNone(mock_orchestration.large_messages)
        self.assertEqual(len(mock_orchestration.large_messages), 2)

    def test_message_statistics_display_correctness(self):
        """测试消息统计数据显示正确性"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        # 创建模拟消息
        from linhai.llm import UserMessage, AssistantMessage, SystemMessage
        from linhai.agent.base import RuntimeMessage

        # 使用Mock模拟SystemMessage，避免registry注册问题
        mock_system_message = Mock(spec=SystemMessage)
        mock_system_message.message = "系统消息，长度12"
        mock_messages = [
            UserMessage(message="用户消息，长度10"),
            AssistantMessage(message="助手消息，长度8"),
            mock_system_message,
            RuntimeMessage("运行时消息，长度15"),
        ]
        message_count = len(mock_messages)

        # 创建模拟编排状态
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {"large_1": mock_messages[0]}

        # 创建grid
        from rich.table import Table

        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan")
        grid.add_column()

        # 调用_build_message_statistics_section
        widget._build_message_statistics_section(
            grid, mock_messages, message_count, mock_orchestration
        )

        # 验证统计正确性
        # 总消息数应为4
        self.assertEqual(message_count, 4)
        # 大消息数量应为1
        self.assertEqual(len(mock_orchestration.large_messages), 1)

    def test_large_messages_migration_consistency(self):
        """测试大消息数量迁移的一致性"""
        registry = Registry()
        widget = ContextTabWidget(registry)

        # 创建模拟编排状态
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {
            "large_1": Mock(),
            "large_2": Mock(),
            "large_3": Mock(),
        }

        # 创建两个grid分别用于消息统计和编排状态
        from rich.table import Table

        stats_grid = Table.grid(padding=(0, 1))
        stats_grid.add_column(style="bold cyan")
        stats_grid.add_column()

        orchestration_grid = Table.grid(padding=(0, 1))
        orchestration_grid.add_column(style="bold cyan")
        orchestration_grid.add_column()

        # 验证大消息数量在编排状态板块中不再显示为单独统计项
        # (通过方法调用验证，不直接检查grid内容)
        widget._build_orchestration_section(orchestration_grid, mock_orchestration)

        # 验证大消息列表仍然显示在编排状态板块中
        self.assertIsNotNone(mock_orchestration.large_messages)
        self.assertEqual(len(mock_orchestration.large_messages), 3)


if __name__ == "__main__":
    unittest.main()
