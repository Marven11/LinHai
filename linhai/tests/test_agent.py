"""Unit tests for the agent module."""

# pylint: disable=protected-access,redefined-outer-name,import-outside-toplevel
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any
from pathlib import Path

from linhai.agent import Agent, AgentContext
from linhai.agent.base import RuntimeMessage
from linhai.llm import ChatMessage
from linhai.tool.main import ToolResultMessage
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.llm import SystemMessage, OpenAi


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

        config: AgentContext = {
            "system_prompt": "Test system prompt",
            "mcp": [],  # 添加mcp字段
            "config_basedir": Path("/tmp"),  # 添加config_basedir字段
            "llms": [self.mock_llm],  # 改为列表
            "llm_names": ["test_llm"],  # 添加llm_names字段
            "current_llm_index": 0,  # 添加当前LLM索引
            "compress_threshold_soft": 500,
            "compress_threshold_hard": 800,
            "tool_confirmation": {
                "skip_confirmation": True,
                "whitelist": ["add_numbers"],
            },
        }

        # 使用GroupChat架构
        self.group_chat = GroupChat()

        # 注意：Agent会在初始化时注册agent_user_input队列，但需要cli_agent_output队列用于输出
        self.group_chat.register_queue("cli_agent_output")

        # 创建真实的ToolManager实例
        self.tool_manager = ToolManager(
            group_chat=self.group_chat, toolsets=[global_tools]
        )
        # 不需要手动注册，ToolManager会在初始化时自动注册到group_chat

        # 创建初始消息列表
        init_messages = [
            SystemMessage(
                template="Test system prompt",
                current_time="2025-10-26 17:00:00",  # 测试用固定时间
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
        self.agent.handle_user_message(test_msg)
        await self.agent.generate_response()

        # 验证 cli_agent_output 队列收到了正确的 tokens 和最终 Answer
        tokens = []
        final_answer = None

        while not self.agent.group_chat.is_empty("cli_agent_output"):
            item = await self.agent.group_chat.receive("cli_agent_output")
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
        self.agent.handle_user_message(user_msg)
        await self.agent.generate_response()

        # 验证用户消息被添加到messages中
        self.assertEqual(
            len(self.agent.messages),
            4,
            f"Messages: {[str(msg) for msg in self.agent.messages]}",
        )  # 系统消息 + 用户消息 + 助手回复 + 运行时消息
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

        # 测试工具消息处理 - 工具消息应该通过其他方式处理，不是通过handle_user_message
        # 这里我们模拟工具消息的处理：直接将工具消息添加到messages中
        self.agent.messages.append(tool_msg)
        
        # 然后模拟LLM处理工具结果
        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2
        
        # 模拟处理工具结果后的LLM响应
        await self.agent.generate_response()

        # 验证工具消息被添加到messages中
        self.assertEqual(
            len(self.agent.messages),
            7,
            f"Messages: {[str(msg) for msg in self.agent.messages]}",
        )  # 系统消息 + 用户消息 + 助手回复 + 运行时消息 + 工具消息 + 助手回复 + 运行时消息
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
            self.agent.handle_user_message(test_msg)
            await self.agent.generate_response()

        self.assertEqual(str(cm.exception), "Test error")
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_run_loop(self):
        """Test agent run loop functionality."""
        # Setup
        self.agent.state_waiting_user = AsyncMock()
        self.agent.state_working = AsyncMock()
        # self.agent.state_paused = AsyncMock()  # 这个属性不存在，注释掉

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
        self.agent.handle_user_message(
            ChatMessage(role="user", message="Calculate 2+2")
        )
        await self.agent.generate_response()

        # 验证tool_manager.process_tool_call被调用
        self.tool_manager.process_tool_call.assert_called_once()
        tool_call = self.tool_manager.process_tool_call.call_args[0][0]
        self.assertEqual(tool_call.function_name, "add_numbers")
        self.assertEqual(tool_call.function_arguments, {"a": 2, "b": 2})

        # 验证状态转换
        self.assertEqual(self.agent.state, "working")

    async def test_at_system_logic(self):
        """测试@系统逻辑，在接收到用户消息时更新LLM索引"""
        # 设置多个LLM用于测试
        mock_llm1 = MagicMock(spec=OpenAi)
        mock_llm2 = MagicMock(spec=OpenAi)

        # 设置answer_stream为AsyncMock，返回一个简单的空响应
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
                    return ChatMessage(role="assistant", message="")

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

        # 测试场景1: 有效的@qwen消息，应该更新索引到1
        self.agent.handle_user_message(ChatMessage(role="user", message="@qwen Hello"))
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引更新为1
        model = await self.agent._select_model()
        self.assertEqual(model, mock_llm2)  # 应该返回第二个LLM

        # 测试场景2: 无效的@invalid消息，索引不应更新，并添加错误消息
        self.agent.context["current_llm_index"] = 0  # 重置索引
        self.agent.handle_user_message(
            ChatMessage(role="user", message="@invalid command")
        )
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引不变
        model = await self.agent._select_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM
        # 验证添加了错误消息
        self.assertTrue(
            any(
                isinstance(msg, RuntimeMessage)
                and "错误：用户指定的LLM名称'invalid'不存在，请向用户报告这一点" in str(msg)
                for msg in self.agent.messages
            )
        )

        # 测试场景3: 没有@消息，索引不应更新
        self.agent.context["current_llm_index"] = 0  # 重置索引
        self.agent.handle_user_message(ChatMessage(role="user", message="Hello world"))
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引不变
        model = await self.agent._select_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM

        # 测试场景4: 多个消息，只有@消息更新索引
        self.agent.context["current_llm_index"] = 0  # 重置索引
        # 先发送一个@qwen消息
        self.agent.handle_user_message(ChatMessage(role="user", message="@qwen first"))
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引更新为1
        # 然后发送一个普通消息
        self.agent.handle_user_message(
            ChatMessage(role="user", message="Normal message")
        )
        self.assertEqual(self.agent.context["current_llm_index"], 1)  # 索引不变
        # 然后发送一个@deepseek-reasoning消息
        self.agent.handle_user_message(
            ChatMessage(role="user", message="@deepseek-reasoning second")
        )
        self.assertEqual(self.agent.context["current_llm_index"], 0)  # 索引更新为0
        model = await self.agent._select_model()
        self.assertEqual(model, mock_llm1)  # 应该返回第一个LLM


if __name__ == "__main__":
    unittest.main()
