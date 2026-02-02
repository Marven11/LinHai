"""Unit tests for the agent module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any

from linhai.agent import Lifecycle
from linhai.llm import UserMessage, AssistantMessage
from linhai.agent.base import RuntimeMessage


class MockAnswerToken(TypedDict):
    """Mock implementation of AnswerToken for testing."""

    reasoning_content: str | None
    content: str


class MockAnswer:
    """Mock implementation of Answer for testing."""

    def __init__(self, tokens: list[MockAnswerToken]):
        self.tokens = tokens
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.tokens):
            raise StopAsyncIteration
        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_message(self) -> AssistantMessage:
        """Get the message content from the tokens."""
        content = "".join(token["content"] for token in self.tokens)
        return AssistantMessage(message=content)

    def get_tool_call(self) -> dict[str, Any] | None:
        """Get the tool call from the tokens, if any."""
        return None

    def get_current_content(self) -> str:
        """Get the current accumulated response content."""
        return "".join(token["content"] for token in self.tokens[: self.index])

    def get_reasoning_message(self) -> str | None:
        """Get the reasoning message from the tokens."""
        return None


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Lifecycle class."""

    def setUp(self):
        from linhai.group_chat import GroupChat

        self.group_chat = GroupChat()
        self.lifecycle = Lifecycle(self.group_chat)
        self.mock_agent = MagicMock()
        self.mock_agent.state = "waiting_user"
        self.mock_agent.current_disable_waiting_user_warning = False
        self.mock_agent.message_processor = MagicMock()
        self.mock_agent.message_processor.get_messages.return_value = []
        self.mock_agent.get_current_model = MagicMock()
        self.mock_agent.get_threshold_info = MagicMock(
            return_value=(80000, 40000, 40000, 0.5)
        )
        self.mock_answer = MagicMock()
        self.mock_answer.get_reasoning_message.return_value = None
        self.mock_tool_call = MagicMock()
        self.mock_tool_result = MagicMock()

        self.mock_issue_manager = MagicMock()
        self.mock_issue_manager.has_unanswered_issues.return_value = False

        # 模拟 machine_control
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_members_side_effect(member_type, member_class=None):
            if member_type == "agent":
                return self.mock_agent
            elif member_type == "issue_manager":
                return self.mock_issue_manager
            elif member_type == "machine_control":
                return self.mock_machine_control
            else:
                return None

        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)

    async def test_register_and_trigger_before_message_generation(self):
        """Test registering and triggering before message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        await self.lifecycle.trigger_before_message_generation(True, False)

        callback1.assert_called_once_with(True, False)
        callback2.assert_called_once_with(True, False)

    async def test_register_and_trigger_after_message_generation(self):
        """Test registering and triggering after message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        self.lifecycle.register_after_message_generation(callback1)
        self.lifecycle.register_after_message_generation(callback2)

        await self.lifecycle.trigger_after_message_generation(
            self.mock_answer, "test response", []
        )

        callback1.assert_called_once_with(self.mock_answer, "test response", [])
        callback2.assert_called_once_with(self.mock_answer, "test response", [])

    async def test_register_and_trigger_on_tool_result(self):
        """Test registering and triggering on tool result callbacks."""
        callback1 = AsyncMock(return_value=None)
        callback2 = AsyncMock(return_value=None)

        self.lifecycle.register_on_tool_result(callback1)
        self.lifecycle.register_on_tool_result(callback2)

        # 测试status="skipped"情况
        await self.lifecycle.trigger_on_tool_result(
            tool_name="test_tool",
            tool_index=0,
            status="skipped",
            message=None,
            toolcall_arguments={"arg1": "value1"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        # 验证回调被调用，但不检查具体参数，因为on_tool_result的参数较多
        callback1.assert_called_once()
        callback2.assert_called_once()

    async def test_register_and_trigger_on_tool_result_success(self):
        """Test registering and triggering on tool result callbacks with success status."""
        callback1 = AsyncMock(return_value=None)
        callback2 = AsyncMock(return_value=None)

        self.lifecycle.register_on_tool_result(callback1)
        self.lifecycle.register_on_tool_result(callback2)

        # 测试status="success"情况
        await self.lifecycle.trigger_on_tool_result(
            tool_name="test_tool",
            tool_index=0,
            status="success",
            message=RuntimeMessage("tool result content"),
            toolcall_arguments=None,
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        callback1.assert_called_once()
        callback2.assert_called_once()

    async def test_callback_order(self):
        """Test that callbacks are triggered in registration order."""
        call_order = []

        async def callback1(_enable_compress, _disable_waiting_user_warning):
            call_order.append(1)

        async def callback2(_enable_compress, _disable_waiting_user_warning):
            call_order.append(2)

        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        await self.lifecycle.trigger_before_message_generation(True, False)

        self.assertEqual(call_order, [1, 2])

    async def test_callback_exception_handling(self):
        """Test that exceptions in callbacks are propagated."""

        async def failing_callback(_enable_compress, _disable_waiting_user_warning):
            raise RuntimeError("Callback failed")

        async def succeeding_callback(_enable_compress, _disable_waiting_user_warning):
            pass

        self.lifecycle.register_before_message_generation(failing_callback)
        self.lifecycle.register_before_message_generation(succeeding_callback)

        with self.assertRaises(RuntimeError) as cm:
            await self.lifecycle.trigger_before_message_generation(True, False)
        self.assertEqual(str(cm.exception), "Callback failed")

    async def test_empty_callbacks(self):
        """Test triggering when no callbacks are registered."""
        try:
            await self.lifecycle.trigger_before_message_generation(True, False)
            await self.lifecycle.trigger_after_message_generation(
                self.mock_answer, "test response", []
            )
            await self.lifecycle.trigger_on_tool_result(
                tool_name="test_tool",
                tool_index=0,
                status="skipped",
                message=None,
                toolcall_arguments={"arg": "value"},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            await self.lifecycle.trigger_before_waiting_user(self.mock_agent)
        except (RuntimeError, asyncio.CancelledError):
            self.fail("Triggering empty callbacks should not throw exceptions")

    async def test_register_and_trigger_before_waiting_user(self):
        """Test registering and triggering before waiting user callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        self.lifecycle.register_before_waiting_user(callback1)
        self.lifecycle.register_before_waiting_user(callback2)

        await self.lifecycle.trigger_before_waiting_user(self.mock_agent)

        callback1.assert_called_once_with(self.mock_agent)
        callback2.assert_called_once_with(self.mock_agent)


if __name__ == "__main__":
    unittest.main()
