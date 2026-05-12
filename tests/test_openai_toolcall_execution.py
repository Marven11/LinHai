import unittest
from unittest.mock import Mock, AsyncMock

from linhai.agent.toolcall import AgentToolcall, EARLY_RETURN_SKIP_MESSAGE
from linhai.agent.state_machine import AgentStateMachine
from linhai.base import ToolCallMessage, OpenAiToolResultMessage
from linhai.type_hints import ParsedOpenAiToolCall
from linhai.tool.base import (
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
)


class _Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_message_processor = Mock()
        self.mock_message_processor.add_openai_tool_result = AsyncMock()
        self.mock_message_processor.get_messages.return_value = []
        self.mock_lifecycle = Mock()
        self.mock_lifecycle.after_toolcall.trigger = AsyncMock(return_value=None)
        self.mock_lifecycle.before_tool_call.trigger = AsyncMock(return_value=None)
        self.mock_tool_manager = Mock()
        self.mock_tool_manager.toolsets = []
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test_llm")
        mock_llm.get_token_limit = Mock(return_value=65536)
        self.mock_llm_manager = Mock()
        self.mock_llm_manager.llms = [mock_llm]
        self.mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.mock_state_machine = Mock(spec=AgentStateMachine)
        self.mock_state_machine.state = "waiting_user"
        self.mock_state_machine.transition_to_working = Mock(
            side_effect=lambda: setattr(self.mock_state_machine, "state", "working")
        )

        def get_member(name, t):
            return {
                "tool_manager": self.mock_tool_manager,
                "llm_manager": self.mock_llm_manager,
                "state_machine": self.mock_state_machine,
                "agent_message": self.mock_message_processor,
                "lifecycle": self.mock_lifecycle,
            }[name]

        self.mock_registry = Mock()
        self.mock_registry.send_if_exists = AsyncMock()
        self.mock_registry.get_member_typechecked = Mock(side_effect=get_member)
        self.processor = AgentToolcall(self.mock_registry)


def _make_tc(id: str, name: str, arguments: dict | None = None) -> ParsedOpenAiToolCall:
    return ParsedOpenAiToolCall(
        type="success",
        id=id,
        name=name,
        arguments=arguments if arguments is not None else {},
    )


class TestCallOpenaiToolsSingleSuccess(_Base):
    async def test_single_tool_call_success(self):
        tc = _make_tc("call_1", "read_file", {"path": "/tmp/x"})
        mock_result = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=1,
            result=SuccessfulToolResult(content="file content"),
            toolcall_arguments={},
        )
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)

        await self.processor.call_openai_tools([tc])

        self.assertFalse(self.processor.early_return)
        self.mock_message_processor.add_openai_tool_result.assert_called_once()
        msg = self.mock_message_processor.add_openai_tool_result.call_args[0][0]
        self.assertIsInstance(msg, OpenAiToolResultMessage)
        self.assertEqual(msg.tool_call_id, "call_1")
        self.assertEqual(msg.content, "file content")


class TestCallOpenaiToolsMultipleSuccess(_Base):
    async def test_multiple_tool_calls_success(self):
        tc1 = _make_tc("call_a", "tool_a")
        tc2 = _make_tc("call_b", "tool_b")
        mock_result = ToolCallResultMessage(
            tool_name="tool_a",
            tool_index=1,
            result=SuccessfulToolResult(content="ok"),
            toolcall_arguments={},
        )
        mock_result2 = ToolCallResultMessage(
            tool_name="tool_b",
            tool_index=2,
            result=SuccessfulToolResult(content="ok2"),
            toolcall_arguments={},
        )
        self.mock_tool_manager.process_tool_call = AsyncMock(
            side_effect=[mock_result, mock_result2]
        )

        await self.processor.call_openai_tools([tc1, tc2])

        self.assertFalse(self.processor.early_return)
        self.assertEqual(
            self.mock_message_processor.add_openai_tool_result.call_count, 2
        )


class TestCallOpenaiToolsEarlyReturn(_Base):
    async def test_early_return_skips_remaining(self):
        tc1 = _make_tc("call_1", "fail_tool")
        tc2 = _make_tc("call_2", "good_tool")
        mock_fail = ToolCallResultMessage(
            tool_name="fail_tool",
            tool_index=1,
            result=FailedToolResult(content="error"),
            toolcall_arguments={},
        )
        self.mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_fail)

        await self.processor.call_openai_tools([tc1, tc2])

        self.assertTrue(self.processor.early_return)
        self.assertEqual(
            self.mock_message_processor.add_openai_tool_result.call_count, 2
        )
        skip_msg = self.mock_message_processor.add_openai_tool_result.call_args_list[1][
            0
        ][0]
        self.assertIsInstance(skip_msg, OpenAiToolResultMessage)
        self.assertEqual(skip_msg.tool_call_id, "call_2")
        self.assertEqual(skip_msg.content, EARLY_RETURN_SKIP_MESSAGE)


class TestCallOpenaiToolsBeforeCallbackBlocks(_Base):
    async def test_before_tool_call_blocks(self):
        tc = _make_tc("call_x", "blocked_tool")
        self.mock_lifecycle.before_tool_call.trigger = AsyncMock(
            return_value=FailedToolResult(content="blocked by policy")
        )

        await self.processor.call_openai_tools([tc])

        self.assertTrue(self.processor.early_return)
        msg = self.mock_message_processor.add_openai_tool_result.call_args[0][0]
        self.assertIsInstance(msg, OpenAiToolResultMessage)
        self.assertEqual(msg.content, "blocked by policy")


class TestCallOpenaiToolsExistingEarlyReturn(_Base):
    async def test_existing_early_return_adds_skip_messages(self):
        self.processor.early_return = True
        tc1 = _make_tc("call_1", "tool_a")
        tc2 = _make_tc("call_2", "tool_b")

        await self.processor.call_openai_tools([tc1, tc2])

        self.assertEqual(
            self.mock_message_processor.add_openai_tool_result.call_count, 2
        )
        self.mock_tool_manager.process_tool_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
