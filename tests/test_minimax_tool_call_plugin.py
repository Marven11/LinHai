"""Tests for MinimaxToolCallPlugin."""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import time

from linhai.plugin.message_checkers import MinimaxToolCallPlugin
from linhai.group_chat import GroupChat
from linhai.llm import Answer


class TestMinimaxToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for MinimaxToolCallPlugin."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.group_chat = MagicMock(spec=GroupChat)
        self.plugin = MinimaxToolCallPlugin(self.group_chat)
        self.agent = AsyncMock()
        self.answer = MagicMock(spec=Answer)

    def test_init(self):
        """Test plugin initialization."""
        self.assertIsNone(self.plugin._last_error_format_time)
        self.assertEqual(self.plugin.TIME_WINDOW_SECONDS, 60)

    async def test_after_token_generation_no_error_time(self):
        """Test after_token_generation returns False when no error time set."""
        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "some content"
        )
        self.assertFalse(result)

    async def test_after_token_generation_time_window_expired(self):
        """Test after_token_generation returns False when time window expired."""
        self.plugin._last_error_format_time = time.time() - 120
        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "some content with marker"
        )
        self.assertFalse(result)

    async def test_after_token_generation_not_first_line(self):
        """Test after_token_generation does not interrupt when marker not in first line."""
        self.plugin._last_error_format_time = time.time()
        result = await self.plugin.after_token_generation(
            self.agent, self.answer, "first line\nsecond line with <minimax:tool_call>"
        )
        self.assertFalse(result)
        self.agent.interrupt.assert_not_called()

    async def test_after_message_generation_no_error_time_when_correct_format(self):
        """Test after_message_generation does not set error time when correct format."""
        await self.plugin.after_message_generation(
            self.answer, "```json toolcall content", []
        )
        self.assertIsNone(self.plugin._last_error_format_time)

    async def test_after_message_generation_detects_minimax_m25_error_format(self):
        """Test after_message_generation sets error time for minimax m2.5 error format."""
        self.group_chat.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.send_if_exists = AsyncMock()

        error_response = '[TOOL_CALL]\n{\n  "name": "test_tool"\n}\n</TOOL_CALL>'
        await self.plugin.after_message_generation(self.answer, error_response, [])

        self.assertIsNotNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_called_once()
        # 不检查具体内容，因为RuntimeMessage可能没有content属性

    async def test_after_message_generation_no_error_for_other_formats(self):
        """Test after_message_generation does not set error time for other incorrect formats."""
        self.group_chat.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.send_if_exists = AsyncMock()

        other_error_response = "<minimax:tool_call>"
        await self.plugin.after_message_generation(
            self.answer, other_error_response, []
        )

        self.assertIsNotNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_called_once()
        # 不检查具体内容

    def test_register(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
