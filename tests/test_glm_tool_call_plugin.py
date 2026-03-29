"""Tests for GlmToolCallPlugin."""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin.message_checkers import GlmToolCallPlugin
from linhai.registry import Registry
from linhai.llm import Answer
from linhai.llm import OpenAi


class MockAgent:
    def __init__(self, compatibility):
        self.model = MagicMock(spec=OpenAi)
        self.model.compatibility = compatibility
        self.model.get_token_limit.return_value = 4096
        self.model.get_name.return_value = "mock-glm"
        self.model.support_image.return_value = False
        self.model.get_explicit_cache_info.return_value = None
        self.message_processor = MagicMock()
        self.message_processor.add_new_message = AsyncMock()

    def get_current_model(self):
        return self.model


class TestGlmToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for GlmToolCallPlugin."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.registry = MagicMock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.plugin = GlmToolCallPlugin(self.registry)
        self.answer = MagicMock(spec=Answer)

    async def test_after_message_generation_non_glm_model(self):
        """Test after_message_generation does nothing for non-GLM models."""
        agent = MockAgent("deepseek")
        self.registry.get_member_typechecked = MagicMock(return_value=agent)

        await self.plugin.after_message_generation(
            self.answer, "<tool_call>some content</tool_call>", []
        )

        agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_glm_model_no_error_format(self):
        """Test after_message_generation does nothing for correct format."""
        agent = MockAgent("glm")
        self.registry.get_member_typechecked = MagicMock(return_value=agent)

        await self.plugin.after_message_generation(
            self.answer, '```json toolcall\n{"name": "test"}\n```', []
        )

        agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    async def test_after_message_generation_glm_model_with_error_format(self):
        """Test after_message_generation warns about GLM error format."""
        agent = MockAgent("glm")
        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        error_response = '<tool_call>\n{"name": "test_tool"}\n</tool_call>'

        await self.plugin.after_message_generation(self.answer, error_response, [])

        agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

        call_args = self.registry.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")
        self.assertIn("GLM错误工具调用格式", call_args[0][1].content)

    async def test_after_message_generation_glm_model_with_error_format_leading_spaces(
        self,
    ):
        """Test after_message_generation detects error format with leading spaces."""
        agent = MockAgent("glm")
        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        error_response = '   <tool_call>\n{"name": "test_tool"}\n</tool_call>'

        await self.plugin.after_message_generation(self.answer, error_response, [])

        agent.message_processor.add_new_message.assert_called_once()
        self.registry.send_if_exists.assert_called_once()

    async def test_after_message_generation_glm_model_normal_response(self):
        """Test after_message_generation does nothing for normal GLM response."""
        agent = MockAgent("glm")
        self.registry.get_member_typechecked = MagicMock(return_value=agent)
        normal_response = "This is a normal response from GLM."

        await self.plugin.after_message_generation(self.answer, normal_response, [])

        agent.message_processor.add_new_message.assert_not_called()
        self.registry.send_if_exists.assert_not_called()

    def test_register(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
