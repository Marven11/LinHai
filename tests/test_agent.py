"""Unit tests for the agent module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any
from pathlib import Path

from linhai.agent import Agent, AgentContext
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, AssistantMessage
from linhai.tool.main import ToolResultMessage
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.llm import SystemMessage, OpenAi


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


class TestAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Agent class."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())

        config: AgentContext = {
            "system_prompt": "Test system prompt",
            "llms": [self.mock_llm],  # 改为列表
            "llm_names": ["test_llm"],  # 添加llm_names字段
            "current_llm_index": 0,  # 添加当前LLM索引
            "compress_threshold": 800,
        }

        self.group_chat = GroupChat()

        self.group_chat.register_queue("agent_answer")

        from linhai.subagent.issue import IssueManager

        self.issue_manager = IssueManager(self.group_chat)

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        init_messages = [
            SystemMessage(
                template="Test system prompt",
                group_chat=self.group_chat,
            )
        ]

        self.agent = Agent(
            context=config,
            group_chat=self.group_chat,
            init_messages=init_messages,
        )

    async def test_initial_state(self):
        """Test agent initial state."""
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_handle_messages(self):
        """Test message handling functionality."""
        test_msg = UserMessage(message="Hello", name="test_user")

        mock_answer = MockAnswer(
            [
                {"reasoning_content": "Thinking...", "content": "Hi"},
                {"reasoning_content": None, "content": " there"},
            ]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.handle_user_message(test_msg)
        await self.agent.generate_response()

        tokens = []
        final_answer = None

        while not self.agent.group_chat.is_empty("agent_answer"):
            item = await self.agent.group_chat.receive("agent_answer")
            if isinstance(item, dict):  # AnswerToken
                tokens.append(item)
            elif hasattr(item, "get_message"):  # 通过鸭子类型检查 Answer 对象
                final_answer = item

        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0]["content"], "Hi")
        self.assertEqual(tokens[1]["content"], " there")

        self.assertIsNotNone(final_answer, "Final Answer object not found")
        assert final_answer is not None  # 让Pylance识别类型
        content = final_answer.get_message().to_llm_message().get("content")
        self.assertIsNotNone(content)
        self.assertEqual(content, "Hi there")

        self.assertEqual(self.agent.state, "waiting_user")

    async def test_message_processing(self):
        """Test message processing functionality."""
        user_msg = UserMessage(message="Hi", name="user")
        tool_msg = ToolResultMessage(content="result")

        mock_answer = MockAnswer(
            [{"reasoning_content": None, "content": "Processing..."}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.handle_user_message(user_msg)
        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertEqual(
            len(messages),
            3,
            f"Messages: {[str(msg) for msg in messages]}",
        )  # 系统消息 + 用户消息 + 助手回复
        self.assertEqual(
            messages[1].to_llm_message().get("content"), "<<user>>Hi<<user>>"
        )
        self.assertEqual(messages[2].to_llm_message().get("content"), "Processing...")

        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2

        self.agent.message_processor.append_message(tool_msg)

        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2

        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertEqual(
            len(messages),
            5,
            f"Messages: {[str(msg) for msg in messages]}",
        )  # 系统消息 + 用户消息 + 助手回复 + 工具消息 + 助手回复
        self.assertEqual(
            messages[3].to_llm_message().get("content"),
            "<<tool>>\n<<message>>工具执行成功<<message>>\n<<data>>result<<data>>\n<<tool>>",
        )
        self.assertEqual(messages[4].to_llm_message().get("content"), "Tool processed")

    async def test_error_handling(self):
        """Test error handling functionality."""
        self.mock_llm.answer_stream.side_effect = RuntimeError("Test error")
        test_msg = UserMessage(message="Error test", name="user")

        with self.assertRaises(RuntimeError) as cm:
            await self.agent.handle_user_message(test_msg)
            await self.agent.generate_response()

        self.assertEqual(str(cm.exception), "Test error")
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_run_loop(self):
        """Test agent run loop functionality."""
        self.agent.state_waiting_user = AsyncMock()
        self.agent.state_working = AsyncMock()

        task_ref = None

        async def mock_state_waiting_user():
            if task_ref:
                task_ref.cancel()

        self.agent.state_waiting_user = AsyncMock(side_effect=mock_state_waiting_user)
        self.agent.state = "waiting_user"

        task_ref = asyncio.create_task(self.agent.run())

        try:
            await asyncio.wait_for(task_ref, timeout=0.5)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            task_ref.cancel()
            self.fail("测试超时，任务未被取消")

        self.agent.state_waiting_user.assert_called_once()

    async def test_markdown_tool_call(self):
        """测试Agent能正确解析markdown格式的工具调用"""
        tool_call_response = """```json toolcall
{
    "name": "add_numbers",
    "arguments": {
        "a": 2,
        "b": 2
    }
}
```"""

        mock_answer = MockAnswer(
            [{"reasoning_content": None, "content": tool_call_response}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        self.tool_manager.process_tool_call = AsyncMock(
            return_value=ToolResultMessage("工具执行成功")
        )

        await self.agent.handle_user_message(UserMessage(message="Calculate 2+2"))
        await self.agent.generate_response()

        self.tool_manager.process_tool_call.assert_called_once()
        tool_call = self.tool_manager.process_tool_call.call_args[0][0]
        self.assertEqual(tool_call.function_name, "add_numbers")
        self.assertEqual(tool_call.function_arguments, {"a": 2, "b": 2})

        self.assertEqual(self.agent.state, "working")

    async def test_at_system_logic(self):
        """测试@系统逻辑，在接收到用户消息时更新LLM索引"""
        mock_llm1 = MagicMock(spec=OpenAi)
        mock_llm2 = MagicMock(spec=OpenAi)

        async def empty_answer_stream(_):
            """返回一个空的答案流。"""

            class EmptyAnswer:
                """空的答案流类。"""

                def __aiter__(self):
                    """返回迭代器自身。"""
                    return self

                async def __anext__(self):
                    """引发StopAsyncIteration。"""
                    raise StopAsyncIteration

                def get_message(self):
                    """返回空消息。"""
                    return AssistantMessage(message="")

                def get_current_content(self):
                    """返回空内容。"""
                    return ""

                def get_reasoning_message(self):
                    """返回None。"""
                    return None

            return EmptyAnswer()

        mock_llm1.answer_stream = AsyncMock(side_effect=empty_answer_stream)
        mock_llm2.answer_stream = AsyncMock(side_effect=empty_answer_stream)

        self.agent.context["llms"] = [mock_llm1, mock_llm2]
        self.agent.context["llm_names"] = ["deepseek-reasoning", "qwen"]
        self.agent.context["current_llm_index"] = 0  # 默认使用第一个

        await self.agent.handle_user_message(UserMessage(message="@qwen Hello"))
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引更新为1
        model = await self.agent.get_current_model()
        self.assertEqual(model, mock_llm2)  # 应该返回第二个LLM

        self.agent.context["current_llm_index"] = 0  # 重置索引
        await self.agent.handle_user_message(UserMessage(message="@invalid command"))
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引不变
        model = await self.agent.get_current_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM
        messages = self.agent.message_processor.get_messages()
        self.assertTrue(
            any(
                isinstance(msg, RuntimeMessage)
                and "错误：用户指定的LLM名称'invalid'不存在，请向用户报告这一点"
                in str(msg)
                for msg in messages
            )
        )

        self.agent.context["current_llm_index"] = 0  # 重置索引
        await self.agent.handle_user_message(UserMessage(message="Hello world"))
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引不变
        model = await self.agent.get_current_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM

        self.agent.context["current_llm_index"] = 0  # 重置索引
        await self.agent.handle_user_message(UserMessage(message="@qwen first"))
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引更新为1
        await self.agent.handle_user_message(UserMessage(message="Normal message"))
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引不变
        await self.agent.handle_user_message(
            UserMessage(message="@deepseek-reasoning second")
        )
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引更新为0
        model = await self.agent.get_current_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM


if __name__ == "__main__":
    unittest.main()
