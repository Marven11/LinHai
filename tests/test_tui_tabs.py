"""测试TUI的标签页功能"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import asyncio
from linhai.tui.app import TUIApp
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.agent.main import Agent


class TestTUITabs(unittest.TestCase):
    """测试TUI的标签页功能"""

    @patch("linhai.tui.app.TUIApp.on_mount")
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
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)
        mock_agent.last_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        mock_agent_message = Mock(spec=AgentMessage)
        mock_agent_message.messages = []
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {}

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)

        from linhai.agent.lifecycle import Lifecycle

        Lifecycle(registry)

        import argparse

        mock_cli_args = argparse.Namespace(planning=False)
        registry.register_member("cli_args", mock_cli_args)

        app = TUIApp(
            registry=registry, tui_config=TUIConfig(), init_messages=[], init_files=[]
        )

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

    @patch("linhai.tui.app.TUIApp.on_mount")
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
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 128000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)
        mock_agent.last_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )

        mock_agent_message = Mock(spec=AgentMessage)
        mock_agent_message.messages = []
        mock_agent_message.pinned_messages = []
        mock_agent_message.notification_messages = {}
        mock_orchestration = Mock(spec=AgentContextOrchestration)
        mock_orchestration.large_messages = {}

        registry.register_member("agent", mock_agent)
        registry.register_member("agent_message", mock_agent_message)
        registry.register_member("agent_context_orchestration", mock_orchestration)

        from linhai.agent.lifecycle import Lifecycle

        Lifecycle(registry)

        import argparse

        mock_cli_args = argparse.Namespace(planning=False)
        registry.register_member("cli_args", mock_cli_args)

        app = TUIApp(
            registry=registry, tui_config=TUIConfig(), init_messages=[], init_files=[]
        )

        async with app.run_test() as pilot:
            agent_pane = pilot.app.query_one("#agent-tab")
            self.assertIsNotNone(agent_pane)


if __name__ == "__main__":
    unittest.main()
