"""测试CLI的标签页功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.cli.app import CLIApp
from linhai.registry import Registry
from linhai.config import CLIConfig
from linhai.agent.main import Agent


class TestCLITabs(unittest.TestCase):
    """测试CLI的标签页功能"""

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_tabs_display(self, mock_on_mount):
        """测试标签页是否正确显示"""
        mock_on_mount.return_value = None

        registry = Registry()
        mock_agent = Mock(spec=Agent)
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.llm import AnswerTokenUsage

        # 配置mock_agent以支持ContextTabWidget
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "usage_ratio": 0.75,
        }
        mock_agent.last_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        mock_agent_message = Mock(spec=AgentMessage)
        mock_agent_message.messages = []
        mock_agent_message.notification_messages = {}
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {}

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)

        # 注册lifecycle模拟对象
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        registry.register_member("lifecycle", mock_lifecycle)

        # 注册cli_args模拟对象
        import argparse

        mock_cli_args = argparse.Namespace(message=None, file=None, planning=False)
        registry.register_member("cli_args", mock_cli_args)

        app = CLIApp(registry=registry, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                tabbed_content = pilot.app.query_one("#main-tabs")
                self.assertIsNotNone(tabbed_content)

                agent_tab = pilot.app.query_one("#agent-tab")
                self.assertIsNotNone(agent_tab)

        asyncio.run(_run_test())

    def test_tabs_functionality(self):
        """测试标签页功能"""
        asyncio.run(self._test_tabs_functionality())

    @patch("linhai.cli.app.CLIApp.on_mount")
    async def _test_tabs_functionality(self, mock_on_mount):
        """异步测试标签页切换功能"""
        mock_on_mount.return_value = None

        registry = Registry()
        mock_agent = Mock(spec=Agent)
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.llm import AnswerTokenUsage

        # 配置mock_agent以支持ContextTabWidget
        mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "usage_ratio": 0.75,
        }
        mock_agent.last_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        mock_agent_message = Mock(spec=AgentMessage)
        mock_agent_message.messages = []
        mock_agent_message.notification_messages = {}
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {}

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)

        # 注册lifecycle模拟对象
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        registry.register_member("lifecycle", mock_lifecycle)

        # 注册cli_args模拟对象
        import argparse

        mock_cli_args = argparse.Namespace(message=None, file=None, planning=False)
        registry.register_member("cli_args", mock_cli_args)

        app = CLIApp(registry=registry, cli_config=CLIConfig())

        async with app.run_test() as pilot:
            agent_pane = pilot.app.query_one("#agent-tab")
            self.assertIsNotNone(agent_pane)


if __name__ == "__main__":
    unittest.main()
