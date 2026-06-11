"""Unit tests for agent marker validation."""

import json
import reprlib
import unittest
from unittest.mock import AsyncMock, MagicMock


from linhai.agent import Agent
from linhai.agent.messages import WAITING_USER_MARKER, RuntimeMessage
from linhai.plugin import WaitingUserPlugin
from linhai.base import UserMessage, AssistantMessage, SystemMessage
from linhai.tool.base import SuccessfulToolResult, ToolCallResultMessage

r = reprlib.Repr()
r.maxstring = 200
custom_repr = r.repr


def format_messages_for_assert(messages):
    """格式化消息列表用于断言错误信息"""
    return (
        f"Messages: {[f'{type(msg).__name__}: {custom_repr(msg)}' for msg in messages]}"
    )


class MockAnswer:
    """Mock implementation of Answer for testing."""

    def __init__(self, content: str):
        """Initialize MockAnswer with content."""
        self.content = content
        from linhai.base import AnswerToken

        self.tokens = [AnswerToken(reasoning_content=None, content=content)]
        self.index = 0

    def __aiter__(self):
        """Return iterator."""
        return self

    async def __anext__(self):
        """Get next token."""
        if self.index >= len(self.tokens):
            raise StopAsyncIteration
        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_message(self) -> AssistantMessage:
        """Get message from content."""
        return AssistantMessage(message=self.content)

    def get_current_content(self) -> str:
        """Get current content."""
        return self.content

    def get_reasoning_message(self) -> str | None:
        """Get reasoning message."""
        return None


class TestAgentMarkerValidation(unittest.IsolatedAsyncioTestCase):
    """Test cases for agent marker validation."""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock()
        self.mock_llm.get_name = MagicMock(return_value="test-llm")
        self.mock_llm.get_explicit_cache_info = MagicMock(return_value=None)

        config = {
            "llms": [self.mock_llm],
            "llm_names": ["test-llm"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.registry = MagicMock()
        self.registry.register_queue = MagicMock()
        self.registry.register_member = MagicMock()
        self.registry.receive = AsyncMock()
        self.registry.send = AsyncMock()
        self.registry.send_if_exists = AsyncMock()
        self.registry.is_empty = MagicMock(return_value=True)
        self.registry.get_member_typechecked = MagicMock()

        self.tool_manager = MagicMock()
        self.tool_manager.get_tools_info.return_value = []
        self.tool_manager.process_tool_call = AsyncMock()
        self.tool_manager.get_workflow.return_value = None

        self.issue_manager = MagicMock()
        self.issue_manager.has_unanswered_issues.return_value = False

        self.lifecycle_mock = MagicMock()
        self.lifecycle_mock.after_toolcall.trigger = AsyncMock(return_value=None)
        self.lifecycle_mock.before_tool_call.trigger = AsyncMock(return_value=None)
        self.lifecycle_mock.after_selecting_llm.trigger = AsyncMock()
        self.lifecycle_mock.on_llm_error.trigger = AsyncMock()

        async def trigger_before_add_new_message_coroutine(msg):
            return None

        self.lifecycle_mock.before_add_new_message.trigger = (
            trigger_before_add_new_message_coroutine
        )

        from linhai.machine_control import MachineControl

        self.mock_machine_control = MagicMock(spec=MachineControl)
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            elif member_type == "issue_manager":
                return self.issue_manager
            elif member_type == "tool_manager":
                return self.tool_manager
            elif member_type == "lifecycle":
                return self.lifecycle_mock
            elif member_type == "agent_message":
                return self.agent.message_processor
            elif member_type == "agent_context_orchestration":
                return self.agent.orchestration
            elif member_type == "state_machine":
                return self.agent.state_machine
            elif member_type == "machine_control":
                return self.mock_machine_control
            elif member_type == "conversation_folder":
                from pathlib import Path
                from tempfile import TemporaryDirectory

                self.temp_dir = TemporaryDirectory()
                self.addCleanup(self.temp_dir.cleanup)
                return Path(self.temp_dir.name)
            elif member_type == "cli_args":
                import argparse

                return argparse.Namespace(afk=False, disable_waiting_marker=False)
            elif member_type == "llm_manager":
                return llm_manager
            elif member_type == "token_manager":
                return self.token_manager
            elif member_type == "task_supervisor":
                if not hasattr(self, "_task_supervisor"):
                    from linhai.task_supervisor import PlainTaskSupervisor

                    self._task_supervisor = PlainTaskSupervisor()
                return self._task_supervisor
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        pinned_messages = [
            SystemMessage(
                registry=self.registry,
            )
        ]

        from linhai.llm_manager import LlmManager

        llm_manager = LlmManager(
            registry=self.registry,
            llms=config["llms"],
            default_llm_name=config["llm_names"][config["current_llm_index"]],
            llm_fallback_map={"test-llm": None},
            llm_fallback_duration_map={"test-llm": 120},
        )

        from linhai.token_manager import TokenManager

        self.token_manager = MagicMock()
        self.token_manager.current_token_usage = None

        self.agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=config["compress_threshold"],
            registry=self.registry,
            pinned_messages=pinned_messages,
        )

        plugin = WaitingUserPlugin(self.registry)
        plugin.register(self.agent.lifecycle)

    async def test_marker_not_in_last_line(self):
        """Test agent adds error message when WAITING_USER_MARKER is not in last line."""
        response_content = f"Some response\n{WAITING_USER_MARKER}\nExtra content"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertEqual(
            len(messages),
            4,  # System + user + assistant + error msg
            format_messages_for_assert(messages),
        )
        error_msgs = [
            msg
            for msg in messages
            if isinstance(msg, RuntimeMessage) and "不在最后一行" in msg.message
        ]
        self.assertGreater(
            len(error_msgs),
            0,
            f"No error message found with '不在最后一行' in messages: {format_messages_for_assert(messages)}",
        )
        error_msg = error_msgs[0]
        self.assertIsInstance(error_msg, RuntimeMessage)
        assert isinstance(error_msg, RuntimeMessage)  # satisfy pylint
        self.assertIn("不在最后一行", error_msg.message)
        self.assertEqual(self.agent.state_machine.state, "waiting_user")

    async def test_both_tool_calls_and_marker(self):
        """Test agent adds error message when both tool calls and marker are present."""
        tool_call_data = {
            "name": "add_numbers",
            "arguments": {"a": 2, "b": 2},
        }
        tool_call_json = json.dumps(tool_call_data)
        response_content = (
            f"Some response with {WAITING_USER_MARKER}\n"
            f"```json toolcall\n{tool_call_json}\n```"
        )
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        tool_result = ToolCallResultMessage(
            tool_name="add_numbers",
            tool_index=0,
            result=SuccessfulToolResult(content="tool result"),
            toolcall_arguments={"a": 2, "b": 2},
        )
        self.tool_manager.process_tool_call = AsyncMock(return_value=tool_result)

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertEqual(
            len(messages),
            5,  # System + user + assistant + tool msg + error msg
            format_messages_for_assert(messages),
        )
        error_msgs = [
            msg
            for msg in messages
            if isinstance(msg, RuntimeMessage) and "既调用了工具又使用了" in msg.message
        ]
        self.assertGreater(
            len(error_msgs),
            0,
            f"No error message found with '既调用了工具又使用了' in messages: {format_messages_for_assert(messages)}",
        )
        error_msg = error_msgs[0]
        self.assertIsInstance(error_msg, RuntimeMessage)
        assert isinstance(error_msg, RuntimeMessage)  # satisfy pylint
        self.assertIn("既调用了工具又使用了", error_msg.message)

    async def test_no_tool_calls_no_marker_in_working_state(self):
        """Test agent adds warning message when no tool calls and no marker in working state."""
        response_content = "Some response without marker or tool calls"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        self.agent.state_machine.state = "working"

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        messages = self.agent.message_processor.get_messages()
        self.assertEqual(
            len(messages),
            4,  # System + user + assistant + warning msg
            format_messages_for_assert(messages),
        )
        warning_msgs = [
            msg
            for msg in messages
            if isinstance(msg, RuntimeMessage)
            and "既没有调用工具，也没有使用" in msg.message
        ]
        self.assertGreater(
            len(warning_msgs),
            0,
            f"No warning message found with '既没有调用工具，也没有使用' in messages: {format_messages_for_assert(messages)}",
        )
        warning_msg = warning_msgs[0]
        self.assertIsInstance(warning_msg, RuntimeMessage)
        assert isinstance(warning_msg, RuntimeMessage)
        self.assertIn("既没有调用工具，也没有使用", warning_msg.message)

    async def test_marker_in_last_line_no_error(self):
        """Test agent does not add error message when WAITING_USER_MARKER is in last line."""
        response_content = f"Some response\n{WAITING_USER_MARKER}"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        self.assertEqual(
            len(self.agent.message_processor.get_messages()),
            3,  # System + user + assistant (conversation保存消息已移除)
            format_messages_for_assert(self.agent.message_processor.get_messages()),
        )
        self.assertEqual(self.agent.state_machine.state, "waiting_user")
        runtime_msgs = [
            msg
            for msg in self.agent.message_processor.get_messages()
            if isinstance(msg, RuntimeMessage) and "既调用了工具又使用了" in msg.message
        ]
        self.assertEqual(len(runtime_msgs), 0)

    async def test_only_tool_calls_no_error(self):
        """Test agent does not add error message when only tool calls are present."""
        tool_call_data = {"name": "add_numbers", "arguments": {"a": 2, "b": 2}}
        tool_call_json = json.dumps(tool_call_data)
        response_content = f"Some response\n```json toolcall\n{tool_call_json}\n```"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        tool_result = ToolCallResultMessage(
            tool_name="add_numbers",
            tool_index=0,
            result=SuccessfulToolResult(content="tool result"),
            toolcall_arguments={"a": 2, "b": 2},
        )
        self.tool_manager.process_tool_call = AsyncMock(return_value=tool_result)

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        self.assertEqual(
            len(self.agent.message_processor.get_messages()),
            4,  # System + user + assistant + tool result
            format_messages_for_assert(self.agent.message_processor.get_messages()),
        )
        runtime_msgs = [
            msg
            for msg in self.agent.message_processor.get_messages()
            if isinstance(msg, RuntimeMessage) and "既调用了工具又使用了" in msg.message
        ]
        self.assertEqual(len(runtime_msgs), 0)

    async def test_only_marker_no_error(self):
        """Test agent does not add error message when only marker is present."""
        response_content = f"Some response with {WAITING_USER_MARKER}"
        mock_answer = MockAnswer(response_content)
        self.mock_llm.answer_stream.return_value = mock_answer

        await self.agent.message_processor.add_new_message(UserMessage(message="Test"))
        await self.agent.generate_response()

        self.assertEqual(
            len(self.agent.message_processor.get_messages()),
            3,  # System + user + assistant
            format_messages_for_assert(self.agent.message_processor.get_messages()),
        )
        self.assertEqual(self.agent.state_machine.state, "waiting_user")
        runtime_msgs = [
            msg
            for msg in self.agent.message_processor.get_messages()
            if isinstance(msg, RuntimeMessage) and "既调用了工具又使用了" in msg.message
        ]
        self.assertEqual(len(runtime_msgs), 0)


if __name__ == "__main__":
    unittest.main()
