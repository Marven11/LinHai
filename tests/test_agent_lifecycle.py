"""Unit tests for the agent module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any

from linhai.agent import Lifecycle
from linhai.llm import ChatMessage



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

    def get_message(self) -> ChatMessage:
        """Get the message content from the tokens."""
        content = "".join(token["content"] for token in self.tokens)
        return ChatMessage(role="assistant", message=content)

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
        self.mock_answer = MagicMock()
        self.mock_answer.get_reasoning_message.return_value = None
        self.mock_tool_call = MagicMock()
        self.mock_tool_result = MagicMock()
        
        # 模拟clarification_manager
        self.mock_clarification_manager = MagicMock()
        self.mock_clarification_manager.has_unanswered_clarifications.return_value = False
        
        # 模拟group_chat.get_members根据参数返回不同的Mock（同步返回）
        def get_members_side_effect(member_type, member_class=None):
            if member_type == "agent":
                return self.mock_agent
            elif member_type == "clarification_manager":
                return self.mock_clarification_manager
            else:
                return None
        
        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)

    async def test_register_and_trigger_before_message_generation(self):
        """Test registering and triggering before message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_message_generation(
            True, False
        )

        # 验证回调被调用
        callback1.assert_called_once_with(True, False)
        callback2.assert_called_once_with(True, False)

    async def test_register_and_trigger_after_message_generation(self):
        """Test registering and triggering after message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_after_message_generation(callback1)
        self.lifecycle.register_after_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_after_message_generation(
            self.mock_answer, "test response", []
        )

        # 验证回调被调用
        callback1.assert_called_once_with(
            self.mock_answer, "test response", []
        )
        callback2.assert_called_once_with(
            self.mock_answer, "test response", []
        )

    async def test_register_and_trigger_before_tool_call(self):
        """Test registering and triggering before tool call callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_before_tool_call(callback1)
        self.lifecycle.register_before_tool_call(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_tool_call(
            self.mock_tool_call
        )

        # 验证回调被调用
        callback1.assert_called_once_with(self.mock_tool_call)
        callback2.assert_called_once_with(self.mock_tool_call)

    async def test_register_and_trigger_after_tool_call(self):
        """Test registering and triggering after tool call callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_after_tool_call(callback1)
        self.lifecycle.register_after_tool_call(callback2)

        # 触发回调
        await self.lifecycle.trigger_after_tool_call(
            self.mock_agent, self.mock_tool_call, self.mock_tool_result, True
        )

        # 验证回调被调用
        callback1.assert_called_once_with(
            self.mock_agent, self.mock_tool_call, self.mock_tool_result, True
        )
        callback2.assert_called_once_with(
            self.mock_agent, self.mock_tool_call, self.mock_tool_result, True
        )

    async def test_callback_order(self):
        """Test that callbacks are triggered in registration order."""
        call_order = []

        async def callback1(_enable_compress, _disable_waiting_user_warning):
            call_order.append(1)

        async def callback2(_enable_compress, _disable_waiting_user_warning):
            call_order.append(2)

        # 注册回调
        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_message_generation(
            True, False
        )

        # 验证回调顺序
        self.assertEqual(call_order, [1, 2])

    async def test_callback_exception_handling(self):
        """Test that exceptions in callbacks are propagated."""

        async def failing_callback(
            _enable_compress, _disable_waiting_user_warning
        ):
            raise RuntimeError("Callback failed")

        async def succeeding_callback(
            _enable_compress, _disable_waiting_user_warning
        ):
            pass

        # 注册回调
        self.lifecycle.register_before_message_generation(failing_callback)
        self.lifecycle.register_before_message_generation(succeeding_callback)

        # 触发回调 - 根据重构，异常应该被传播
        with self.assertRaises(RuntimeError) as cm:
            await self.lifecycle.trigger_before_message_generation(
                True, False
            )
        self.assertEqual(str(cm.exception), "Callback failed")

        # 验证第二个回调仍然被调用
        # 由于是mock测试，我们主要验证没有异常抛出

    async def test_empty_callbacks(self):
        """Test triggering when no callbacks are registered."""
        # 触发没有注册回调的事件 - 应该不会抛出异常
        try:
            await self.lifecycle.trigger_before_message_generation(
                True, False
            )
            await self.lifecycle.trigger_after_message_generation(
                self.mock_answer, "test response", []
            )
            await self.lifecycle.trigger_before_tool_call(
                self.mock_tool_call
            )
            await self.lifecycle.trigger_after_tool_call(
                self.mock_agent, self.mock_tool_call, self.mock_tool_result, True
            )
            await self.lifecycle.trigger_before_waiting_user(
                self.mock_agent
            )
            await self.lifecycle.trigger_tool_success(
                self.mock_agent, self.mock_tool_call, self.mock_tool_result
            )
            # 模拟agent.current_answer.get_current_content返回字符串而不是MagicMock
            self.mock_agent.current_answer = MagicMock()
            self.mock_agent.current_answer.get_current_content = MagicMock(return_value="")
            await self.lifecycle.trigger_tool_failure(
                self.mock_agent, self.mock_tool_call, "test error"
            )
            await self.lifecycle.trigger_tool_parse_error(
                self.mock_agent, "parse error message"
            )
            # 模拟subagent_manager
            mock_subagent_manager = MagicMock()
            mock_subagent_manager.create_subagent = AsyncMock()
            def get_members_side_effect(member_type, member_class=None):
                members = {
                    "agent": self.mock_agent,
                    "clarification_manager": self.mock_clarification_manager,
                    "subagent_manager": mock_subagent_manager
                }
                return members.get(member_type)
            self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)
            await self.lifecycle.trigger_tool_conflict(
                self.mock_agent, self.mock_tool_call, ["tool1", "tool2"]
            )
        except (RuntimeError, asyncio.CancelledError):
            self.fail("Triggering empty callbacks should not throw exceptions")

    async def test_register_and_trigger_before_waiting_user(self):
        """Test registering and triggering before waiting user callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_before_waiting_user(callback1)
        self.lifecycle.register_before_waiting_user(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_waiting_user(self.mock_agent)

        # 验证回调被调用
        callback1.assert_called_once_with(self.mock_agent)
        callback2.assert_called_once_with(self.mock_agent)


if __name__ == "__main__":
    unittest.main()
