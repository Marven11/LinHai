"""Unit tests for the agent module."""

import asyncio
import json
import unittest
from asyncio import Queue
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any

from linhai.agent import Agent, AgentConfig, Lifecycle
from linhai.llm import (
    ChatMessage,
    AnswerToken,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.tool.main import ToolResultMessage


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


class TestAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Agent class."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "model": self.mock_llm,
            "compress_threshold_soft": 500,  # 使用正确的键
            "compress_threshold_hard": 800,  # 使用正确的键
            "tool_confirmation": {
                "skip_confirmation": True,  # 跳过确认
                "whitelist": ["add_numbers"],  # 将 add_numbers 加入白名单
            },
        }
        self.user_input_queue: "Queue[ChatMessage]" = Queue()
        self.user_output_queue: "Queue[AnswerToken | Answer]" = Queue()
        self.tool_request_queue: "Queue[ToolCallMessage]" = Queue()
        self.tool_confirmation_queue: "Queue[ToolConfirmationMessage]" = Queue()
        self.tool_manager = MagicMock()
        self.tool_manager.get_tools_info.return_value = []
        self.tool_manager.process_tool_call = AsyncMock()
        self.tool_manager.get_workflow.return_value = None
        self.agent = Agent(
            config=config,
            user_input_queue=self.user_input_queue,
            user_output_queue=self.user_output_queue,
            tool_request_queue=self.tool_request_queue,
            tool_confirmation_queue=self.tool_confirmation_queue,
            tool_manager=self.tool_manager,
        )

    async def test_initial_state(self):
        """Test agent initial state."""
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_handle_messages(self):
        """Test message handling functionality."""
        # Setup
        test_msg = ChatMessage(role="user", message="Hello", name="test_user")

        # 模拟 answer_stream 返回一个 MockAnswer
        mock_answer = MockAnswer(
            [
                {"reasoning_content": "Thinking...", "content": "Hi"},
                {"reasoning_content": None, "content": " there"},
            ]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        # Test
        await self.agent.handle_messages([test_msg])

        # 验证 user_output_queue 收到了正确的 tokens 和最终 Answer
        tokens = []
        final_answer = None

        while not self.agent.user_output_queue.empty():
            item = await self.agent.user_output_queue.get()
            if isinstance(item, dict):  # AnswerToken
                tokens.append(item)
            elif hasattr(item, "get_message"):  # 通过鸭子类型检查 Answer 对象
                final_answer = item

        # 验证 token 内容
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0]["content"], "Hi")
        self.assertEqual(tokens[1]["content"], " there")

        # 验证最终 Answer 对象
        self.assertIsNotNone(final_answer, "Final Answer object not found")
        assert final_answer is not None  # 让Pylance识别类型
        content = final_answer.get_message().to_llm_message().get("content")
        self.assertIsNotNone(content)
        self.assertEqual(content, "Hi there")

        # 验证上下文更新
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_state_transitions(self):
        """Test agent state transitions."""
        # Test state transitions
        self.agent.state = "working"
        self.assertEqual(self.agent.state, "working")

        self.agent.state = "paused"
        self.assertEqual(self.agent.state, "paused")

    async def test_message_processing(self):
        """Test message processing functionality."""
        # Setup
        user_msg = ChatMessage(role="user", message="Hi", name="user")
        tool_msg = ToolResultMessage(content="result")

        # 创建MockAnswer对象并设置LLM mock
        mock_answer = MockAnswer(
            [{"reasoning_content": None, "content": "Processing..."}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        # 测试用户消息处理
        await self.agent.handle_messages([user_msg])

        # 验证用户消息被添加到messages中
        self.assertEqual(
            len(self.agent.messages), 5
        )  # 系统消息 + 全局记忆 + 廉价LLM状态 + 用户消息 + 回复
        self.assertEqual(
            self.agent.messages[3].to_llm_message().get("content"), "<user>Hi</user>"
        )
        self.assertEqual(
            self.agent.messages[4].to_llm_message().get("content"), "Processing..."
        )

        # 重置mock以便测试工具消息
        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2

        # 测试工具消息处理 - 直接调用handle_messages
        await self.agent.handle_messages([tool_msg])

        # 验证工具消息被添加到messages中
        self.assertEqual(
            len(self.agent.messages), 7
        )  # 系统消息 + 全局记忆 + 廉价LLM状态 + 用户消息 + 回复 + 工具消息 + 回复
        # 工具消息被添加到末尾
        self.assertEqual(
            self.agent.messages[5].to_llm_message().get("content"), "result"
        )
        # 验证工具处理后的回复
        self.assertEqual(
            self.agent.messages[6].to_llm_message().get("content"), "Tool processed"
        )

    async def test_error_handling(self):
        """Test error handling functionality."""
        # Setup error
        self.mock_llm.answer_stream.side_effect = RuntimeError("Test error")
        test_msg = ChatMessage(role="user", message="Error test", name="user")

        # Test and verify exception is raised
        with self.assertRaises(RuntimeError) as cm:
            await self.agent.handle_messages([test_msg])

        self.assertEqual(str(cm.exception), "Test error")
        self.assertEqual(self.agent.state, "paused")

    async def test_run_loop(self):
        """Test agent run loop functionality."""
        # Setup
        self.agent.state_waiting_user = AsyncMock()
        self.agent.state_working = AsyncMock()
        self.agent.state_paused = AsyncMock()

        # 创建任务引用
        task_ref = None

        # 设置state_waiting_user模拟方法，使其在调用时取消任务
        async def mock_state_waiting_user():
            # 取消任务以退出循环
            if task_ref:
                task_ref.cancel()

        self.agent.state_waiting_user = AsyncMock(side_effect=mock_state_waiting_user)
        self.agent.state = "waiting_user"

        # 创建并运行任务
        task_ref = asyncio.create_task(self.agent.run())

        try:
            # 等待任务完成（会被mock_state_waiting_user取消）
            await asyncio.wait_for(task_ref, timeout=0.5)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            task_ref.cancel()
            self.fail("测试超时，任务未被取消")

        # 验证state_waiting_user被调用
        self.agent.state_waiting_user.assert_called_once()

    async def test_markdown_tool_call(self):
        """测试Agent能正确解析markdown格式的工具调用"""
        # 模拟LLM返回包含工具调用的markdown响应
        tool_call_response = """```json
{
    "name": "add_numbers",
    "arguments": {
        "a": 2,
        "b": 2
    }
}
```"""

        # 创建MockAnswer对象
        mock_answer = MockAnswer(
            [{"reasoning_content": None, "content": tool_call_response}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        # 设置tool_manager的process_tool_call模拟
        self.tool_manager.process_tool_call = AsyncMock()

        # 发送用户消息触发处理
        await self.agent.handle_messages(
            [ChatMessage(role="user", message="Calculate 2+2")]
        )

        # 验证tool_manager.process_tool_call被调用
        self.tool_manager.process_tool_call.assert_called_once()
        tool_call = self.tool_manager.process_tool_call.call_args[0][0]
        self.assertEqual(tool_call.function_name, "add_numbers")
        self.assertEqual(tool_call.function_arguments, {"a": 2, "b": 2})

        # 验证状态转换
        self.assertEqual(self.agent.state, "working")


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
