"""Unit tests for agent marker validation."""

import asyncio
import json
import reprlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from asyncio import Queue

# 创建自定义repr函数，限制长度为200字符
r = reprlib.Repr()
r.maxstring = 200
custom_repr = r.repr

def format_messages_for_assert(messages):
    """格式化消息列表用于断言错误信息"""
    return f"Messages: {[f'{type(msg).__name__}: {custom_repr(msg)}' for msg in messages]}"

from linhai.agent import Agent, AgentConfig
from linhai.llm import (
    ChatMessage,
    AnswerToken,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.agent_base import WAITING_USER_MARKER, RuntimeMessage
from linhai.tool.main import ToolResultMessage


class MockAnswer:
    """Mock implementation of Answer for testing."""

    def __init__(self, content: str):
        self.content = content
        self.tokens = [{"reasoning_content": None, "content": content}]

    def __aiter__(self):
        self.index = 0
        return self

    async def __anext__(self):
        if self.index >= len(self.tokens):
            raise StopAsyncIteration
        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_message(self) -> ChatMessage:
        return ChatMessage(role="assistant", message=self.content)

    def get_current_content(self) -> str:
        return self.content


class TestAgentMarkerValidation(unittest.IsolatedAsyncioTestCase):
    """Test cases for agent marker validation."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock()

        config: AgentConfig = {
            "system_prompt": "Test system prompt",
            "model": self.mock_llm,
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": ["add_numbers"],
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

        # 创建初始消息列表
        from linhai.llm import SystemMessage
        init_messages = [SystemMessage("Test system prompt")]

        self.agent = Agent(
            config=config,
            user_input_queue=self.user_input_queue,
            user_output_queue=self.user_output_queue,
            tool_request_queue=self.tool_request_queue,
            tool_confirmation_queue=self.tool_confirmation_queue,
            tool_manager=self.tool_manager,
            init_messages=init_messages,
        )

    async def test_marker_not_in_last_line(self):
        """Test agent adds error message when WAITING_USER_MARKER is not in last line."""
        # Mock LLM response with marker not in last line
        response_content = f"Some response\n{WAITING_USER_MARKER}\nExtra content"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if error message was added
        self.assertEqual(
            len(self.agent.messages), 4,  # System + user + assistant + error
            format_messages_for_assert(self.agent.messages)
        )
        error_msg = self.agent.messages[-1]
        self.assertIsInstance(error_msg, RuntimeMessage)
        assert isinstance(error_msg, RuntimeMessage)  # satisfy pylint
        self.assertIn("不在最后一行", error_msg.message)
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_both_tool_calls_and_marker(self):
        """Test agent adds error message when both tool calls and marker are present."""
        # Mock LLM response with both tool calls and marker
        tool_call_data = {
            "name": "add_numbers",
            "arguments": json.dumps({"a": 2, "b": 2}),
        }
        tool_call_json = json.dumps(tool_call_data)
        response_content = f"Some response with {WAITING_USER_MARKER}\n```json toolcall\n{tool_call_json}\n```"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Mock tool manager to return a ToolResultMessage
        tool_result = ToolResultMessage(content="tool result")
        self.tool_manager.process_tool_call = AsyncMock(return_value=tool_result)

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if error message was added
        self.assertEqual(
            len(self.agent.messages), 6,  # System + user + assistant + empty user + runtime for tool call + error (tool result not added due to conflict)
            format_messages_for_assert(self.agent.messages)
        )
        error_msg = self.agent.messages[-1]
        self.assertIsInstance(error_msg, RuntimeMessage)
        assert isinstance(error_msg, RuntimeMessage)  # satisfy pylint
        self.assertIn("既调用了工具又使用了", error_msg.message)

    async def test_no_tool_calls_no_marker_in_working_state(self):
        """Test agent adds warning message when no tool calls and no marker in working state."""
        # Mock LLM response without tool calls or marker
        response_content = "Some response without marker or tool calls"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Set agent to working state
        self.agent.state = "working"

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if warning message was added
        self.assertEqual(
            len(self.agent.messages), 4,  # System + user + assistant + warning
            format_messages_for_assert(self.agent.messages)
        )
        warning_msg = self.agent.messages[-1]
        self.assertIsInstance(warning_msg, RuntimeMessage)
        assert isinstance(warning_msg, RuntimeMessage)
        self.assertIn("警告", warning_msg.message)
        self.assertIn("等待用户回答", warning_msg.message)

    async def test_marker_in_last_line_no_error(self):
        """Test agent does not add error message when WAITING_USER_MARKER is in last line."""
        # Mock LLM response with marker in last line
        response_content = f"Some response\n{WAITING_USER_MARKER}"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if no error message was added
        self.assertEqual(
            len(self.agent.messages), 3,  # System + user + assistant
            format_messages_for_assert(self.agent.messages)
        )
        self.assertEqual(self.agent.state, "waiting_user")
        # Verify no error messages
        runtime_msgs = [
            msg for msg in self.agent.messages if isinstance(msg, RuntimeMessage)
        ]
        self.assertEqual(len(runtime_msgs), 0)

    async def test_only_tool_calls_no_error(self):
        """Test agent does not add error message when only tool calls are present."""
        # Mock LLM response with only tool calls
        tool_call_data = {"name": "add_numbers", "arguments": {"a": 2, "b": 2}}
        tool_call_json = json.dumps(tool_call_data)
        response_content = f"Some response\n```json toolcall\n{tool_call_json}\n```"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Mock tool manager to return a ToolResultMessage
        tool_result = ToolResultMessage(content="tool result")
        self.tool_manager.process_tool_call = AsyncMock(return_value=tool_result)

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if no error message was added
        self.assertEqual(
            len(self.agent.messages), 5,  # System + user + assistant + runtime for tool call + tool result
            format_messages_for_assert(self.agent.messages)
        )
        # Verify no error messages related to marker validation
        runtime_msgs = [
            msg
            for msg in self.agent.messages
            if isinstance(msg, RuntimeMessage) and "既调用了工具又使用了" in msg.message
        ]
        self.assertEqual(len(runtime_msgs), 0)

    async def test_only_marker_no_error(self):
        """Test agent does not add error message when only marker is present."""
        # Mock LLM response with only marker
        response_content = f"Some response with {WAITING_USER_MARKER}"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        # Send user message to trigger processing
        await self.agent.handle_messages([ChatMessage(role="user", message="Test")])

        # Check if no error message was added
        self.assertEqual(
            len(self.agent.messages), 3,  # System + user + assistant
            format_messages_for_assert(self.agent.messages)
        )
        self.assertEqual(self.agent.state, "waiting_user")
        # Verify no error messages
        runtime_msgs = [
            msg for msg in self.agent.messages if isinstance(msg, RuntimeMessage)
        ]
        self.assertEqual(len(runtime_msgs), 0)


if __name__ == "__main__":
    unittest.main()
