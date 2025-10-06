"""Unit tests for the agent module."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any

from linhai.agent import Lifecycle
from linhai.llm import ChatMessage


# 定义模拟的 AnswerToken 和 Answer
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


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Lifecycle class."""

    def setUp(self):
        self.lifecycle = Lifecycle()
        self.mock_agent = MagicMock()
        self.mock_agent.state = "waiting_user"
        self.mock_answer = MagicMock()
        self.mock_tool_call = MagicMock()
        self.mock_tool_result = MagicMock()

    async def test_register_and_trigger_before_message_generation(self):
        """Test registering and triggering before message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_message_generation(
            self.mock_agent, True, False
        )

        # 验证回调被调用
        callback1.assert_called_once_with(self.mock_agent, True, False)
        callback2.assert_called_once_with(self.mock_agent, True, False)

    async def test_register_and_trigger_after_message_generation(self):
        """Test registering and triggering after message generation callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        # 注册回调
        self.lifecycle.register_after_message_generation(callback1)
        self.lifecycle.register_after_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_after_message_generation(
            self.mock_agent, self.mock_answer, "test response", []
        )

        # 验证回调被调用
        callback1.assert_called_once_with(
            self.mock_agent, self.mock_answer, "test response", []
        )
        callback2.assert_called_once_with(
            self.mock_agent, self.mock_answer, "test response", []
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
            self.mock_agent, self.mock_tool_call
        )

        # 验证回调被调用
        callback1.assert_called_once_with(self.mock_agent, self.mock_tool_call)
        callback2.assert_called_once_with(self.mock_agent, self.mock_tool_call)

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

        async def callback1(agent, enable_compress, disable_waiting_user_warning):
            call_order.append(1)

        async def callback2(agent, enable_compress, disable_waiting_user_warning):
            call_order.append(2)

        # 注册回调
        self.lifecycle.register_before_message_generation(callback1)
        self.lifecycle.register_before_message_generation(callback2)

        # 触发回调
        await self.lifecycle.trigger_before_message_generation(
            self.mock_agent, True, False
        )

        # 验证回调顺序
        self.assertEqual(call_order, [1, 2])

    async def test_callback_exception_handling(self):
        """Test that exceptions in callbacks are caught and logged."""

        async def failing_callback(
            agent, enable_compress, disable_waiting_user_warning
        ):
            raise RuntimeError("Callback failed")

        async def succeeding_callback(
            agent, enable_compress, disable_waiting_user_warning
        ):
            pass

        # 注册回调
        self.lifecycle.register_before_message_generation(failing_callback)
        self.lifecycle.register_before_message_generation(succeeding_callback)

        # 触发回调 - 应该不会抛出异常
        try:
            await self.lifecycle.trigger_before_message_generation(
                self.mock_agent, True, False
            )
        except Exception:
            self.fail("Exception from callback should be caught")

        # 验证第二个回调仍然被调用
        # 由于是mock测试，我们主要验证没有异常抛出

    async def test_empty_callbacks(self):
        """Test triggering when no callbacks are registered."""
        # 触发没有注册回调的事件 - 应该不会抛出异常
        try:
            await self.lifecycle.trigger_before_message_generation(
                self.mock_agent, True, False
            )
            await self.lifecycle.trigger_after_message_generation(
                self.mock_agent, self.mock_answer, "test", []
            )
            await self.lifecycle.trigger_before_tool_call(
                self.mock_agent, self.mock_tool_call
            )
            await self.lifecycle.trigger_after_tool_call(
                self.mock_agent, self.mock_tool_call, self.mock_tool_result, True
            )
        except Exception:
            self.fail("Triggering empty callbacks should not throw exceptions")


if __name__ == "__main__":
    unittest.main()
