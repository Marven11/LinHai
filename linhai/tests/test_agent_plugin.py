"""Unit tests for agent plugins."""

import unittest
from unittest.mock import MagicMock

from linhai.agent_plugin import (
    WaitingUserPlugin,
    ToolCallCountPlugin,
    ThinkingToolCallPlugin,
)
from linhai.agent_base import WAITING_USER_MARKER, RuntimeMessage
from unittest.mock import AsyncMock
from linhai.llm import Answer


class TestWaitingUserPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for WaitingUserPlugin."""

    def setUp(self):
        self.plugin = WaitingUserPlugin()
        self.agent = MagicMock()
        self.agent.state = "working"
        self.answer = MagicMock()

    async def test_marker_in_last_line(self):
        """Test when WAITING_USER_MARKER is in the last line."""
        full_response = f"Some response\n{WAITING_USER_MARKER}"

        await self.plugin.after_message_generation(self.agent, self.answer, full_response, [])

        self.agent.messages.append.assert_not_called()
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_marker_not_in_last_line(self):
        """Test when WAITING_USER_MARKER is not in the last line."""
        full_response = f"{WAITING_USER_MARKER}\nSome other content"

        await self.plugin.after_message_generation(self.agent, self.answer, full_response, [])

        self.agent.messages.append.assert_called_once()
        call_args = self.agent.messages.append.call_args[0][0]
        self.assertIsInstance(call_args, RuntimeMessage)
        self.assertIn("不在最后一行", call_args.message)
        self.assertEqual(
            self.agent.state, "working"
        )  # 状态应为working，因为标记不在最后一行

    async def test_register_plugin(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


class TestToolCallCountPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for ToolCallCountPlugin."""

    async def asyncSetUp(self):
        self.plugin = ToolCallCountPlugin()
        self.agent = MagicMock()
        self.agent.user_output_queue = AsyncMock()
        self.answer = MagicMock()
        self.answer.content = ""

    async def test_tool_call_within_limit_short_content(self):
        """测试短内容时工具调用在限制内"""
        current_content = 'Some content\n```json\n{"name": "tool1"}\n```\n```json\n{"name": "tool2"}\n```'
        self.answer.content = current_content

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.user_output_queue.put.assert_not_called()
        self.agent.messages.append.assert_not_called()

    async def test_tool_call_exceed_limit_short_content(self):
        """测试短内容时工具调用超过限制"""
        current_content = 'Some content\n```json\n{"name": "tool1"}\n```\n```json\n{"name": "tool2"}\n```\n```json\n{"name": "tool3"}\n```\n```json\n{"name": "tool4"}\n```\n```json\n{"name": "tool5"}\n```\n```json\n{"name": "tool6"}\n```'
        self.answer.content = current_content

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.user_output_queue.put.assert_called_once_with(self.answer)
        self.agent.messages.append.assert_called_once()
        call_args = self.agent.messages.append.call_args[0][0]
        self.assertIn("错误：一次性调用了超过5个工具", call_args.message)
        self.assertTrue(self.answer.interrupted)

    async def test_tool_call_within_limit_long_content(self):
        """测试长内容时工具调用在限制内"""
        current_content = "A" * 2000 + '\n```json\n{"name": "tool1"}\n```'
        self.answer.content = current_content

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.user_output_queue.put.assert_not_called()
        self.agent.messages.append.assert_not_called()

    async def test_tool_call_exceed_limit_long_content(self):
        """测试长内容时工具调用超过限制"""
        current_content = (
            "A" * 2000
            + '\n```json\n{"name": "tool1"}\n```\n```json\n{"name": "tool2"}\n```'
        )
        self.answer.content = current_content

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.user_output_queue.put.assert_called_once_with(self.answer)
        self.agent.messages.append.assert_called_once()
        call_args = self.agent.messages.append.call_args[0][0]
        self.assertIn("错误：一次性调用了超过1个工具", call_args.message)
        self.assertTrue(self.answer.interrupted)


class TestThinkingToolCallPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for ThinkingToolCallPlugin."""

    async def asyncSetUp(self):
        self.plugin = ThinkingToolCallPlugin()
        self.agent = MagicMock()
        self.agent.user_output_queue = AsyncMock()
        self.answer = MagicMock()
        self.answer.reasoning_message = None
        self.answer.set_reasoning_message = lambda message: setattr(
            self.answer, "reasoning_message", message
        )
        self.answer.get_reasoning_message = lambda: self.answer.reasoning_message
        self.answer.content = ""

    async def test_thinking_within_limit(self):
        """测试思考中的工具调用在限制内"""
        current_reasoning = 'Some reasoning\n```json\n{"name": "tool1"}\n```\n```json\n{"name": "tool2"}\n```'
        self.answer.set_reasoning_message(current_reasoning)
        current_content = "Some content"

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.user_output_queue.put.assert_not_called()
        self.agent.messages.append.assert_not_called()

    async def test_thinking_exceed_limit(self):
        """测试思考中的工具调用超过限制"""
        current_reasoning = 'Some reasoning\n```json\n{"name": "tool1"}\n```\n```json\n{"name": "tool2"}\n```\n```json\n{"name": "tool3"}\n```\n```json\n{"name": "tool4"}\n```'
        self.answer.set_reasoning_message(current_reasoning)
        current_content = "Some content"

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.user_output_queue.put.assert_called_once_with(self.answer)
        self.agent.messages.append.assert_called_once()
        call_args = self.agent.messages.append.call_args[0][0]
        self.assertIn("错误：大量思考如何使用```json调用工具", call_args.message)
        self.assertTrue(self.answer.interrupted)

    async def test_thinking_no_json_blocks(self):
        """测试思考中没有JSON块"""
        current_reasoning = "Some reasoning without json blocks"
        self.answer.set_reasoning_message(current_reasoning)
        current_content = "Some content"

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.user_output_queue.put.assert_not_called()
        self.agent.messages.append.assert_not_called()

    async def test_thinking_not_string(self):
        """测试思考内容不是字符串"""
        self.answer.set_reasoning_message(None)
        current_content = "Some content"

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.user_output_queue.put.assert_not_called()
        self.agent.messages.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
