"""Unit tests for the agent module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from typing import TypedDict, Any
from pathlib import Path

from linhai.agent import Agent
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, AssistantMessage
from linhai.tool.base import ToolResultSuccess, ToolCallResultMessage
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.llm import SystemMessage, OpenAi
from linhai.cli.components import RuntimeMessageWidget


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
        token_dict = self.tokens[self.index]

        class Token:
            def __init__(self, reasoning_content, content):
                self.reasoning_content = reasoning_content
                self.content = content

        token = Token(token_dict["reasoning_content"], token_dict["content"])
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
        self.mock_llm.get_name = MagicMock(return_value="test_llm")

        config = {
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.group_chat = GroupChat()

        self.group_chat.register_queue("parsed_agent_answer")

        from linhai.cli.app import CLIApp

        mock_cli_app = MagicMock(spec=CLIApp)
        mock_container = MagicMock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.register_member("cli_app", mock_cli_app)

        from linhai.machine_control import MachineControl

        self.mock_machine_control = MagicMock(spec=MachineControl)
        self.mock_machine_control.target_machine = "master_host"
        self.group_chat.register_member("machine_control", self.mock_machine_control)

        import argparse

        self.group_chat.register_member("cli_args", argparse.Namespace(afk=False))

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        pinned_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            )
        ]

        self.agent = Agent(
            llms=config["llms"],
            compress_threshold=config["compress_threshold"],
            group_chat=self.group_chat,
            pinned_messages=pinned_messages,
            llm_name=config["llm_names"][config["current_llm_index"]],
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

        parsed_answer = None
        while not self.agent.group_chat.is_empty("parsed_agent_answer"):
            item = await self.agent.group_chat.receive("parsed_agent_answer")
            if hasattr(item, "segment_queue"):
                parsed_answer = item
                break

        self.assertIsNotNone(parsed_answer, "ParsedAnswer object not found")

        completed_normally = await parsed_answer.wait_parsing()
        self.assertTrue(completed_normally, "Parsing was interrupted")

        from linhai.llm import AssistantMessage

        content = "Hi there"
        self.assertEqual(self.agent.state, "waiting_user")

        self.assertEqual(self.agent.state, "waiting_user")

    async def test_message_processing(self):
        """Test message processing functionality."""
        user_msg = UserMessage(message="Hi", name="user")
        from linhai.tool.base import ToolCallResultMessage

        tool_msg = ToolCallResultMessage(
            tool_name="dummy_tool",
            tool_index=0,
            result=ToolResultSuccess(content="result"),
            toolcall_arguments=None,
        )

        mock_answer = MockAnswer(
            [{"reasoning_content": None, "content": "Processing..."}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.handle_user_message(user_msg)
        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertGreaterEqual(
            len(messages),
            3,
            f"Messages: {[str(msg) for msg in messages]}",
        )
        self.assertLessEqual(
            len(messages),
            5,
            f"Messages: {[str(msg) for msg in messages]}",
        )
        self.assertEqual(
            messages[1].to_llm_message().get("content"), "<<user>>Hi<<user>>"
        )
        self.assertEqual(messages[2].to_llm_message().get("content"), "Processing...")

        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2

        self.agent.message_processor.add_new_message(tool_msg)

        mock_answer2 = MockAnswer(
            [{"reasoning_content": None, "content": "Tool processed"}]
        )
        self.mock_llm.answer_stream.return_value = mock_answer2

        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertGreaterEqual(
            len(messages),
            5,
            f"Messages: {[str(msg) for msg in messages]}",
        )
        self.assertLessEqual(
            len(messages),
            8,
            f"Messages: {[str(msg) for msg in messages]}",
        )

        tool_result_found = False
        for msg in messages:
            content = msg.to_llm_message().get("content", "")
            if "dummy_tool" in content and "工具执行成功" in content:
                tool_result_found = True
                self.assertEqual(
                    content,
                    "<<tool>>\n<<name>>dummy_tool<<name>>\n<<index>>0<<index>>\n<<message>>工具执行成功<<message>>\n<<data>>result<<data>>\n<<tool>>",
                )
                break
        self.assertTrue(tool_result_found, "未找到工具结果消息")

        assistant_reply_found = False
        for msg in messages:
            content = msg.to_llm_message().get("content", "")
            if content == "Tool processed":
                assistant_reply_found = True
                break
        self.assertTrue(assistant_reply_found, "未找到助手回复消息'Tool processed'")

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
            return_value=ToolCallResultMessage(
                tool_name="add_numbers",
                tool_index=0,
                result=ToolResultSuccess(content="工具执行成功"),
                toolcall_arguments=None,
            )
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
        new_group_chat = GroupChat()

        from linhai.cli.app import CLIApp

        mock_cli_app = MagicMock(spec=CLIApp)
        mock_container = MagicMock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        new_group_chat.register_member("cli_app", mock_cli_app)

        from linhai.tool.main import ToolManager
        from linhai.config import ToolConfig
        from pathlib import Path

        mock_tool_manager = MagicMock(spec=ToolManager)
        mock_tool_manager.group_chat = new_group_chat
        new_group_chat.register_member("tool_manager", mock_tool_manager)

        mock_llm1 = MagicMock(spec=OpenAi)
        mock_llm2 = MagicMock(spec=OpenAi)

        async def empty_answer_stream(_):
            class EmptyAnswer:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise StopAsyncIteration

                def get_message(self):
                    return AssistantMessage(message="")

                def get_current_content(self):
                    return ""

                def get_reasoning_message(self):
                    return None

            return EmptyAnswer()

        mock_llm1.answer_stream = AsyncMock(side_effect=empty_answer_stream)
        mock_llm2.answer_stream = AsyncMock(side_effect=empty_answer_stream)
        mock_llm1.get_name = MagicMock(return_value="deepseek-reasoning")
        mock_llm2.get_name = MagicMock(return_value="qwen")

        from linhai.agent import Agent

        agent = Agent(
            llms=[mock_llm1, mock_llm2],
            compress_threshold=800,
            group_chat=new_group_chat,
            pinned_messages=[],
            llm_name="deepseek-reasoning",
        )

        await agent.handle_user_message(UserMessage(message="@qwen Hello"))
        self.assertEqual(agent.current_llm_index, 1)
        self.assertEqual(agent.llm_names[1], "qwen")

        mock_cli_app.reset_mock()
        mock_container.reset_mock()

        agent.current_llm_index = 0
        await agent.handle_user_message(UserMessage(message="@invalid command"))
        self.assertEqual(agent.current_llm_index, 0)

        mock_cli_app.query_one.assert_called_once_with("#chat-container")
        mock_container.mount.assert_called_once()
        widget = mock_container.mount.call_args[0][0]
        self.assertIsInstance(widget, RuntimeMessageWidget)
        self.assertIn("错误：LLM名称 'invalid' 不存在", widget.content_str)

        agent.current_llm_index = 0
        await agent.handle_user_message(UserMessage(message="Hello world"))
        self.assertEqual(agent.current_llm_index, 0)

        await agent.handle_user_message(UserMessage(message="@qwen first"))
        self.assertEqual(agent.current_llm_index, 1)

        await agent.handle_user_message(UserMessage(message="Normal message"))
        self.assertEqual(agent.current_llm_index, 1)

        await agent.handle_user_message(
            UserMessage(message="@deepseek-reasoning second")
        )
        self.assertEqual(agent.current_llm_index, 0)

    async def test_queue_command(self):
        """测试/queue命令，将消息加入排队列表。"""
        await self.agent.handle_user_message(UserMessage(message="/queue 等下需要实现"))
        self.assertEqual(len(self.agent.queued_messages), 1)
        self.assertEqual(self.agent.queued_messages[0].message, "等下需要实现")


if __name__ == "__main__":
    unittest.main()
