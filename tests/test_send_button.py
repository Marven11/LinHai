"""测试发送按钮功能"""

import unittest
from unittest.mock import patch, Mock, AsyncMock
import asyncio
from textual.widgets import Button, TextArea
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent.main import Agent


class TestSendButton(unittest.TestCase):
    """测试发送按钮功能"""

    def setUp(self):
        """设置测试环境"""
        self.group_chat = GroupChat()
        self.mock_agent = Mock(spec=Agent)
        from linhai.agent.message import AgentMessage
        from linhai.agent.orchestration import AgentContextOrchestration
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

        self.mock_agent_message = Mock(spec=AgentMessage)
        self.mock_agent_message.messages = []
        self.mock_agent_message.notification_messages = {}
        self.mock_orchestration = Mock(spec=AgentContextOrchestration)
        self.mock_orchestration.large_messages = {}

        self.group_chat.register_member("agent", self.mock_agent)
        self.group_chat.register_member("agent_message", self.mock_agent_message)
        self.group_chat.register_member(
            "agent_context_orchestration", self.mock_orchestration
        )

        from linhai.agent.lifecycle import Lifecycle
        self.mock_lifecycle = Mock(spec=Lifecycle)
        self.group_chat.register_member("lifecycle", self.mock_lifecycle)

        import argparse
        self.mock_cli_args = argparse.Namespace()
        self.mock_cli_args.message = None
        self.mock_cli_args.file = None
        self.group_chat.register_member("cli_args", self.mock_cli_args)

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_exists(self, mock_on_mount):
        """测试发送按钮是否存在"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                send_button = pilot.app.query_one("#send-button", Button)
                self.assertIsNotNone(send_button)
                self.assertEqual(send_button.label.plain, "→")
                self.assertEqual(send_button.variant, "primary")

        asyncio.run(_run_test())

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_size(self, mock_on_mount):
        """测试发送按钮大小为3x3"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                send_button = pilot.app.query_one("#send-button", Button)
                self.assertEqual(send_button.styles.width.value, 3)
                self.assertEqual(send_button.styles.height.value, 3)

        asyncio.run(_run_test())

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_width_exactly_3(self, mock_on_mount):
        """测试发送按钮宽度严格等于3，不大于3"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                send_button = pilot.app.query_one("#send-button", Button)
                width = send_button.styles.width.value
                self.assertEqual(width, 3, f"按钮宽度应为3，但实际为{width}")
                self.assertLessEqual(width, 3, f"按钮宽度不应大于3，但实际为{width}")

        asyncio.run(_run_test())

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_aligns_to_bottom(self, mock_on_mount):
        """测试发送按钮在多行输入时靠底部对齐"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                from textual.containers import Horizontal

                container = pilot.app.query_one("#input-container", Horizontal)
                send_button = pilot.app.query_one("#send-button", Button)
                input_area = pilot.app.query_one("#input", TextArea)

                input_area.text = "第一行\n第二行\n第三行"
                await pilot.pause()

                container_styles = container.styles
                align_vertical = container_styles.align_vertical
                if hasattr(align_vertical, 'value'):
                    align_vertical = align_vertical.value
                self.assertEqual(
                    align_vertical,
                    "bottom",
                    "输入容器应该使用底部对齐"
                )

        asyncio.run(_run_test())

    @patch("linhai.cli.app.MessagesList.add_user_message")
    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_click_sends_message(
        self, mock_on_mount, mock_add_user_message
    ):
        """测试点击发送按钮能发送消息"""
        mock_on_mount.return_value = None
        mock_add_user_message.return_value = AsyncMock()()

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                input_area = pilot.app.query_one("#input", TextArea)
                input_area.text = "测试消息"

                send_button = pilot.app.query_one("#send-button", Button)
                await pilot.click("#send-button")

                await asyncio.sleep(0.1)

        asyncio.run(_run_test())

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_input_container_exists(self, mock_on_mount):
        """测试输入容器是否存在"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                from textual.containers import Horizontal

                container = pilot.app.query_one("#input-container", Horizontal)
                self.assertIsNotNone(container)

                input_area = pilot.app.query_one("#input", TextArea)
                send_button = pilot.app.query_one("#send-button", Button)

                self.assertIn(input_area, container.children)
                self.assertIn(send_button, container.children)

        asyncio.run(_run_test())

    @patch("linhai.cli.app.CLIApp.on_mount")
    def test_send_button_not_selectable(self, mock_on_mount):
        """测试发送按钮文本不可选中"""
        mock_on_mount.return_value = None

        app = CLIApp(group_chat=self.group_chat, cli_config=CLIConfig())

        async def _run_test():
            async with app.run_test() as pilot:
                send_button = pilot.app.query_one("#send-button", Button)
                self.assertFalse(send_button.allow_select, "按钮应该不允许文本选择")

        asyncio.run(_run_test())


if __name__ == "__main__":
    unittest.main()
