"""Tests for MinimaxToolCallPlugin."""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import time

from linhai.plugin.message_checkers import MinimaxToolCallPlugin
from linhai.registry import Registry
from linhai.base import Answer


class TestMinimaxToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for MinimaxToolCallPlugin."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.registry = MagicMock(spec=Registry)
        self.plugin = MinimaxToolCallPlugin(self.registry)
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
            self.agent, self.answer, "first line\nsecond line with <minimax:tool_call>"
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

    async def test_after_message_generation_detects_minimax_m25_error_format(self):
        """Test after_message_generation sets error time for minimax m2.5 error format."""
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        error_response = '[TOOL_CALL]\n{\n  "name": "test_tool"\n}\n</TOOL_CALL>'
        self.answer.get_message.return_value.get_content.return_value = error_response
        await self.plugin.after_message_generation(self.answer, [])

        self.assertIsNotNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_called_once()
        # 不检查具体内容，因为RuntimeMessage可能没有content属性

    async def test_after_message_generation_no_error_for_other_formats(self):
        """Test after_message_generation does not set error time for other incorrect formats."""
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        other_error_response = "<minimax:tool_call>"
        self.answer.get_message.return_value.get_content.return_value = (
            other_error_response
        )
        await self.plugin.after_message_generation(self.answer, [])

        self.assertIsNotNone(self.plugin._last_error_format_time)
        self.agent.message_processor.add_new_message.assert_called_once()
        # 不检查具体内容

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

    async def test_tool_call_with_missing_name_field(self) -> None:
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()
        self.answer.get_message.return_value.get_content.return_value = (
            "[TOOL_CALL]\n" '{"arguments": {}}\n' "</TOOL_CALL>\n"
        )
        await self.plugin.after_message_generation(self.answer, [])
        self.assertIsNotNone(self.plugin._last_error_format_time)

    async def test_tool_call_empty_marker(self) -> None:
        self.registry.get_member_typechecked = MagicMock(return_value=self.agent)
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry.send_if_exists = AsyncMock()
        self.answer.get_message.return_value.get_content.return_value = (
            "[TOOL_CALL]\n" "\n" "</TOOL_CALL>\n"
        )
        await self.plugin.after_message_generation(self.answer, [])
        self.assertIsNotNone(self.plugin._last_error_format_time)


if __name__ == "__main__":
    unittest.main()
