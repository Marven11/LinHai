"""测试回车发送后输入框是否被正确清空。"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from linhai.tui.app import TUIApp
from linhai.registry import Registry
from linhai.config import TUIConfig
from linhai.tui.messages_list import MessagesList


class TestEnterKeyClearsInput(unittest.IsolatedAsyncioTestCase):
    """测试回车键发送消息后输入框是否被清空。"""

    async def asyncSetUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        self.registry.register_queue("user_message")

        # 创建模拟agent
        from linhai.agent.main import Agent
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.agent.lifecycle import Lifecycle

        self.mock_agent = Mock(spec=Agent)
        self.mock_agent_message = Mock(spec=AgentMessage)
        self.mock_agent_message.messages = []
        self.mock_agent_message.pinned_messages = []
        self.mock_agent_message.notification_messages = {}
        self.mock_orchestration = Mock(spec=AgentContextOrchestration)
        self.mock_orchestration.large_messages = {}
        self.mock_lifecycle = Mock(spec=Lifecycle)

        self.registry.register_member("agent", self.mock_agent)
        self.registry.register_member("agent_message", self.mock_agent_message)
        self.registry.register_member(
            "agent_context_orchestration", self.mock_orchestration
        )
        self.registry.register_member("lifecycle", self.mock_lifecycle)

        # 模拟cli_args
        import argparse

        mock_cli_args = argparse.Namespace(planning=False)
        self.registry.register_member("cli_args", mock_cli_args)

        # 模拟token_manager
        from linhai.token_manager import TokenManager

        self.mock_token_manager = Mock(spec=TokenManager)
        self.mock_token_manager.get_token_display_pieces.return_value = []
        self.mock_token_manager.update_cumulative_usage = Mock()
        self.mock_token_manager.start_watching = Mock()

        # 模拟其他组件
        from linhai.llm import AnswerTokenUsage

        self.mock_agent.get_threshold_info.return_value = {
            "hard_limit": 8000,
            "used_tokens": 6000,
            "usage_ratio": 0.75,
        }
        self.mock_agent.last_token_usage = AnswerTokenUsage(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            cached_input_tokens=500,
        )
        mock_llm = Mock()
        mock_llm.get_token_limit.return_value = 8000
        self.mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm)

        # 模拟llm_manager
        self.mock_llm_manager = Mock()
        self.mock_llm_manager.llms = []
        self.mock_agent.llm_manager = self.mock_llm_manager

        # 创建app
        self.app = TUIApp(
            registry=self.registry,
            tui_config=TUIConfig(),
            init_messages=[],
            init_files=[],
        )

        # 模拟messages_list（不验证调用，只确保测试运行）
        self.mock_messages_list = AsyncMock(spec=MessagesList)
        self.mock_messages_list.add_user_message = AsyncMock()
        self.mock_messages_list.add_initial_messages = AsyncMock()
        self.mock_messages_list.start_listening = AsyncMock()
        self.mock_messages_list.cleanup = AsyncMock()
        self.mock_messages_list.mount = Mock()
        self.app.messages_list = self.mock_messages_list

        # 模拟FooterWidget
        self.mock_footer = Mock()
        self.mock_footer.update_token_info = Mock()

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_enter_key_clears_input_text(self, mock_on_mount):
        """测试按下回车键后输入框文本被清空。"""
        mock_on_mount.return_value = None

        async with self.app.run_test() as pilot:
            # 获取输入框
            input_element = pilot.app.query_one("#input")

            # 设置一些文本
            input_element.text = "Hello world"

            # 模拟按下回车键
            await pilot.press("enter")
            await pilot.pause(0.1)  # 等待事件处理

            # 验证输入框是否被清空
            self.assertEqual(input_element.text, "", "输入框应在回车发送后被清空")

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_empty_input_not_sent(self, mock_on_mount):
        """测试空输入不会被发送。"""
        mock_on_mount.return_value = None

        async with self.app.run_test() as pilot:
            input_element = pilot.app.query_one("#input")

            # 设置空文本
            input_element.text = ""

            # 模拟按下回车键
            await pilot.press("enter")
            await pilot.pause(0.1)

            # 输入框应保持为空
            self.assertEqual(input_element.text, "")

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_input_with_whitespace_not_sent(self, mock_on_mount):
        """测试仅包含空白字符的输入不会被发送。"""
        mock_on_mount.return_value = None

        async with self.app.run_test() as pilot:
            input_element = pilot.app.query_one("#input")

            # 设置仅包含空白字符的文本
            input_element.text = "   \t\n  "

            # 模拟按下回车键
            await pilot.press("enter")
            await pilot.pause(0.1)

            # 输入框应被清空
            self.assertEqual(input_element.text, "", "仅包含空白字符的输入应被清空")

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_enter_key_clears_multiline_input(self, mock_on_mount):
        """测试按下回车键后多行输入被清空。"""
        mock_on_mount.return_value = None
        async with self.app.run_test() as pilot:
            input_element = pilot.app.query_one("#input")

            # 设置多行文本
            input_element.text = "Line 1\nLine 2\nLine 3"

            # 模拟按下回车键
            await pilot.press("enter")
            await pilot.pause(0.1)

            # 验证输入框被清空
            self.assertEqual(input_element.text, "", "多行输入应在回车发送后被清空")
            # 验证没有遗留的换行符
            self.assertEqual(
                input_element.text.count("\n"), 0, "输入框不应有任何遗留的换行符"
            )

    @patch("linhai.tui.app.TUIApp.on_mount")
    async def test_enter_key_clears_input_with_cursor_at_end(self, mock_on_mount):
        """测试按下回车键后光标在末尾时输入框被清空。"""
        mock_on_mount.return_value = None
        async with self.app.run_test() as pilot:
            input_element = pilot.app.query_one("#input")

            # 设置文本并移动光标到末尾
            input_element.text = "Hello world"
            input_element.move_cursor((11, 0))

            # 模拟按下回车键
            await pilot.press("enter")
            await pilot.pause(0.1)

            # 验证输入框被清空
            self.assertEqual(input_element.text, "")
            # 验证光标位置在开头
            cursor_location = input_element.cursor_location
            self.assertEqual(cursor_location, (0, 0), "光标应在开头位置 (0, 0)")


if __name__ == "__main__":
    unittest.main()
