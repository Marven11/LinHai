"""Tests for KimiK25ToolCallPlugin."""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import time

from linhai.plugin.message_checkers import KimiK25ToolCallPlugin
from linhai.registry import Registry
from linhai.base import Answer


class TestKimiK25ToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for KimiK25ToolCallPlugin."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.registry = MagicMock(spec=Registry)
        self.plugin = KimiK25ToolCallPlugin(self.registry)
        self.agent = AsyncMock()
        self.agent.get_current_model = MagicMock(
            return_value=MagicMock(
                get_native_toolcall_format=MagicMock(return_value=False)
            )
        )
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
            self.agent, self.answer, "first line\nsecond line with marker"
        )
        self.assertFalse(result)
        self.agent.agent_llm.interrupt.assert_not_called()

    async def test_after_message_generation_no_error_time_when_correct_format(self):
        """Test after_message_generation does not set error time when correct format."""
        self.answer.get_message.return_value.get_content.return_value = (
            "```json toolcall content"
        )
        await self.plugin.after_message_generation(self.answer, [])
        self.assertIsNone(self.plugin._last_error_format_time)

    def test_register(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_token_generation.register.assert_called_once_with(
            self.plugin.after_token_generation
        )
        lifecycle.after_message_generation.register.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_tool_call_missing_required_fields(self) -> None:
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()
        self.answer.get_message.return_value.get_content.return_value = (
            "<|tool_call_begin|> {'function': 'incomplete'}\nother"
        )
        await self.plugin.after_message_generation(self.answer, [])
        self.assertIsNotNone(self.plugin._last_error_format_time)

    async def test_tool_call_empty_block(self) -> None:
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()
        self.answer.get_message.return_value.get_content.return_value = (
            "<|tool_call_begin|>\n\nother"
        )
        await self.plugin.after_message_generation(self.answer, [])
        self.assertIsNotNone(self.plugin._last_error_format_time)


if __name__ == "__main__":
    unittest.main()
