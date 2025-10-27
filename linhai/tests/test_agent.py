"""Unit tests for the agent module."""

import asyncio
import unittest
from asyncio import Queue
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any

from linhai.agent import Agent, AgentConfig
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

    def get_reasoning_message(self) -> str | None:
        """Get the reasoning message from the tokens."""
        return None


class TestAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Agent class."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "llms": [self.mock_llm],  # 改为列表
            "current_llm_index": 0,  # 添加当前LLM索引
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": ["add_numbers"],
            },
        }
        
        # 使用GroupChat架构
        from linhai.group_chat import GroupChat
        self.group_chat = GroupChat()
        
        # 注意：Agent会在初始化时注册agent_user_input队列，但需要cli_user_output队列用于输出
        self.group_chat.register_queue("cli_user_output")
        
        # 创建真实的ToolManager实例
        from linhai.tool.main import ToolManager
        from linhai.tool.base import global_tools
        self.tool_manager = ToolManager(group_chat=self.group_chat, toolsets=[global_tools])
        # 不需要手动注册，ToolManager会在初始化时自动注册到group_chat

        # 创建初始消息列表
        from linhai.llm import SystemMessage

        init_messages = [SystemMessage(
            template="Test system prompt",
            current_time="2025-10-26 17:00:00",  # 测试用固定时间
            group_chat=self.group_chat
        )]

        self.agent = Agent(
            config=config,
            group_chat=self.group_chat,
            init_messages=init_messages,
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

        # 验证 cli_user_output 队列收到了正确的 tokens 和最终 Answer
        tokens = []
        final_answer = None

        while not self.agent.group_chat.is_empty("cli_user_output"):
            item = await self.agent.group_chat.receive("cli_user_output")
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
        self.assertEqual(len(self.agent.messages), 4, f"Messages: {[str(msg) for msg in self.agent.messages]}")  # 系统消息 + 用户消息 + 回复 + 任务规划格式检查
        self.assertEqual(
            self.agent.messages[1].to_llm_message().get("content"), "<user>Hi</user>"
        )
        self.assertEqual(
            self.agent.messages[2].to_llm_message().get("content"), "Processing..."
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
            len(self.agent.messages), 7, f"Messages: {[str(msg) for msg in self.agent.messages]}"
        )  # 系统消息 + 用户消息 + 回复 + 任务规划格式检查 + 工具消息 + 回复 + 任务规划格式检查
        # 工具消息被添加到末尾
        self.assertEqual(
            self.agent.messages[4].to_llm_message().get("content"), "result"
        )
        # 验证工具处理后的回复
        self.assertEqual(
            self.agent.messages[5].to_llm_message().get("content"), "Tool processed"
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
        tool_call_response = """```json toolcall
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


if __name__ == "__main__":
    unittest.main()
