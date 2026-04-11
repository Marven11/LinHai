import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin.message_checkers import MisplacedToolCallPlugin
from linhai.agent import Agent
from linhai.base import Answer


class TestMisplacedToolCallPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.registry = MagicMock()
        self.plugin = MisplacedToolCallPlugin(self.registry)

        self.agent = MagicMock(spec=Agent)
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.registry.send_if_exists = AsyncMock()

    async def test_misplaced_tool_call_detected(self) -> None:
        full_response = (
            '让我调用工具```json toolcall\n{"name": "test", "arguments": {}}\n```'
        )

        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, []
        )

        self.agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_correct_tool_call_not_flagged(self) -> None:
        full_response = '```json toolcall\n{"name": "test", "arguments": {}}\n```'

        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, []
        )

        self.agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_multiple_misplaced_detected(self) -> None:
        full_response = (
            '文字```json toolcall\n{"name": "a", "arguments": {}}\n```\n'
            '更多文字```json toolcall\n{"name": "b", "arguments": {}}\n```'
        )

        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, []
        )

        self.agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_issue_example_detected(self) -> None:
        full_response = (
            "我先按照AGENTS.md的启动顺序读取记忆文件，"
            "然后查看issue #607。让我同时读取多个文件喵~```json toolcall "
            '{"name": "read_file", "arguments": {"filepath": "/home/linhai/.local/share/linhai/claw/REMINDER.md"}}'
        )

        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), full_response, []
        )

        self.agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_empty_response_not_flagged(self) -> None:
        await self.plugin.after_message_generation(MagicMock(spec=Answer), "", [])

        self.agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_normal_text_not_flagged(self) -> None:
        await self.plugin.after_message_generation(
            MagicMock(spec=Answer), "这是一段普通文字，没有工具调用", []
        )

        self.agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    def test_plugin_registration(self) -> None:
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
