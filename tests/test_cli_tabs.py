"""测试CLI的标签页功能"""

import unittest
from unittest.mock import patch, Mock
import asyncio
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent.main import Agent


class TestCLITabs(unittest.TestCase):
    """测试CLI的标签页功能"""

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_tabs_display(self, mock_on_mount):
        """测试标签页是否正确显示"""
        mock_on_mount.return_value = None
        
        group_chat = GroupChat()
        mock_agent = Mock(spec=Agent)
        group_chat.register_member("agent", mock_agent)
        
        app = CLIApp(group_chat=group_chat, init_messages=None, cli_config=CLIConfig())
        
        async def _run_test():
            async with app.run_test() as pilot:
                tabbed_content = pilot.app.query_one("#main-tabs")
                self.assertIsNotNone(tabbed_content)
                
                agent_tab = pilot.app.query_one("#agent-tab")
                subagent_tab = pilot.app.query_one("#subagent-tab")
                self.assertIsNotNone(agent_tab)
                self.assertIsNotNone(subagent_tab)
                
                subagent_content = pilot.app.query_one("#subagent-content")
                self.assertIsNotNone(subagent_content)
        
        asyncio.run(_run_test())

    def test_tabs_functionality(self):
        """测试标签页功能"""
        asyncio.run(self._test_tabs_functionality())

    @patch("linhai.cli.app.CLIApp.on_mount")
    async def _test_tabs_functionality(self, mock_on_mount):
        """异步测试标签页切换功能"""
        mock_on_mount.return_value = None
        
        group_chat = GroupChat()
        mock_agent = Mock(spec=Agent)
        group_chat.register_member("agent", mock_agent)
        
        app = CLIApp(group_chat=group_chat, init_messages=None, cli_config=CLIConfig())
        
        async with app.run_test() as pilot:
            agent_pane = pilot.app.query_one("#agent-tab")
            self.assertIsNotNone(agent_pane)
            
            subagent_pane = pilot.app.query_one("#subagent-tab")
            self.assertIsNotNone(subagent_pane)


if __name__ == "__main__":
    unittest.main()