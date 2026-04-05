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
from linhai.registry import Registry
from linhai.tool.main import ToolManager
from linhai.tool.base import utils_tools
from linhai.llm import SystemMessage, OpenAi
from linhai.tui.components import RuntimeMessageWidget
from linhai.task_supervisor import PlainTaskSupervisor


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
        self.registry = Registry()
        self.registry.register_member("task_supervisor", PlainTaskSupervisor())

        self.registry.register_queue("parsed_agent_answer")

        from tempfile import TemporaryDirectory

        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        from pathlib import Path

        conversation_dir = Path(self.temp_dir.name)
        self.registry.register_member("conversation_folder", conversation_dir)

        from linhai.tui.app import TUIApp
        from linhai.tui.messages_list import MessagesList

        mock_cli_app = MagicMock(spec=TUIApp)
        mock_container = MagicMock()
        mock_cli_app.query_one.return_value = mock_container
        # should_auto_scroll现在在MessagesList中，TUIApp不再有这个方法
        self.registry.register_member("tui_app", mock_cli_app)

        # 创建一个mock的MessagesList
        mock_messages_list = MagicMock(spec=MessagesList)
        mock_messages_list.should_auto_scroll.return_value = True
        self.registry.register_member("messages_list", mock_messages_list)

        from linhai.machine_control import MachineControl

        self.mock_machine_control = MagicMock(spec=MachineControl)
        self.mock_machine_control.target_machine = "master_host"
        self.registry.register_member("machine_control", self.mock_machine_control)

        import argparse

        self.registry.register_member("cli_args", argparse.Namespace(afk=False))

        from linhai.config import ToolConfig

        self.tool_manager = ToolManager(
            registry=self.registry,
            toolsets=[utils_tools],
            config=ToolConfig(),
            mcp_connector=None,
        )

        from linhai.token_manager import TokenManager

        self.token_manager = TokenManager(self.registry)

        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())
        self.mock_llm.get_name = MagicMock(return_value="test_llm")
        self.mock_llm.get_explicit_cache_info = MagicMock(return_value=None)

        # 创建LlmManager实例而不是直接传递llms列表
        from linhai.llm_manager import LlmManager

        self.llm_manager = LlmManager(
            registry=self.registry,
            llms=[self.mock_llm],
            default_llm_name="test_llm",
            llm_fallback_map={"test_llm": None},
        )

        config = {
            "llm_manager": self.llm_manager,
            "compress_threshold": 800,
        }

        pinned_messages = [
            SystemMessage(
                registry=self.registry,
            )
        ]

        self.agent = Agent(
            llm_manager=config["llm_manager"],
            compress_threshold=config["compress_threshold"],
            registry=self.registry,
            pinned_messages=pinned_messages,
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

        await self.agent.message_processor.add_new_message(test_msg)
        await self.agent.generate_response()

        parsed_answer = None
        while not self.agent.registry.is_empty("parsed_agent_answer"):
            item = await self.agent.registry.receive("parsed_agent_answer")
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

        await self.agent.message_processor.add_new_message(user_msg)
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

        await self.agent.message_processor.add_new_message(tool_msg)

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
            await self.agent.message_processor.add_new_message(test_msg)
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

        await self.agent.message_processor.add_new_message(
            UserMessage(message="Calculate 2+2")
        )
        await self.agent.generate_response()

        self.tool_manager.process_tool_call.assert_called_once()
        tool_call = self.tool_manager.process_tool_call.call_args[0][0]
        self.assertEqual(tool_call.function_name, "add_numbers")
        self.assertEqual(tool_call.function_arguments, {"a": 2, "b": 2})

        self.assertEqual(self.agent.state, "working")

    async def test_at_system_logic(self):
        """测试@系统逻辑，在接收到用户消息时更新LLM索引"""
        new_registry = Registry()

        from linhai.tui.app import TUIApp
        from linhai.tui.messages_list import MessagesList

        mock_cli_app = MagicMock(spec=TUIApp)
        mock_container = MagicMock()
        mock_cli_app.query_one.return_value = mock_container
        new_registry.register_member("tui_app", mock_cli_app)

        mock_messages_list = MagicMock(spec=MessagesList)
        mock_messages_list.should_auto_scroll.return_value = True
        new_registry.register_member("messages_list", mock_messages_list)

        from tempfile import TemporaryDirectory

        temp_dir = TemporaryDirectory()
        from pathlib import Path

        conversation_dir = Path(temp_dir.name)
        new_registry.register_member("conversation_folder", conversation_dir)

        from linhai.tool.main import ToolManager
        from linhai.config import ToolConfig

        mock_tool_manager = MagicMock(spec=ToolManager)
        mock_tool_manager.registry = new_registry
        new_registry.register_member("tool_manager", mock_tool_manager)

        self.addCleanup(temp_dir.cleanup)

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
        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            registry=new_registry,
            llms=[mock_llm1, mock_llm2],
            default_llm_name="deepseek-reasoning",
            llm_fallback_map={"deepseek-reasoning": None, "qwen": None},
        )

        agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=800,
            registry=new_registry,
            pinned_messages=[],
        )

        async def dispatch(msg: UserMessage):
            await new_registry.send("user_message", msg)
            handler = new_registry.get_member_typechecked(
                "user_message_handler", UserMessageHandler
            )
            await handler.receive_and_dispatch()

        from linhai.agent.user_message_handler import UserMessageHandler

        await dispatch(UserMessage(message="@qwen Hello"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm2)

        mock_cli_app.reset_mock()
        mock_container.reset_mock()

        await agent.llm_manager.switch_to_llm("deepseek-reasoning")
        await dispatch(UserMessage(message="@invalid command"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm1)

        agent.llm_manager.current_llm_index = 0
        await dispatch(UserMessage(message="Hello world"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm1)

        await dispatch(UserMessage(message="@qwen first"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm2)

        await dispatch(UserMessage(message="Normal message"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm2)

        await dispatch(UserMessage(message="@deepseek-reasoning second"))
        current_llm = agent.llm_manager.get_current_llm()
        self.assertEqual(current_llm, mock_llm1)

    async def test_queue_command(self):
        """测试/queue命令，将消息加入排队列表。"""
        from linhai.agent.user_message_handler import UserMessageHandler

        handler = self.registry.get_member_typechecked(
            "user_message_handler", UserMessageHandler
        )
        await self.registry.send(
            "user_message", UserMessage(message="/queue 等下需要实现")
        )
        await handler.receive_and_dispatch()
        self.assertEqual(len(self.agent.message_processor.queued_messages), 1)
        self.assertEqual(
            self.agent.message_processor.queued_messages[0].message, "等下需要实现"
        )


if __name__ == "__main__":
    unittest.main()
