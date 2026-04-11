import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, MagicMock

from linhai.agent.command_callback import CommandCallback
from linhai.agent.user_message_handler import ParsedUserMessage
from linhai.base import UserMessage
from linhai.utils.input_parser import parse_user_input
from linhai.registry import Registry


def make_parsed(msg_text: str) -> ParsedUserMessage:
    msg = UserMessage(message=msg_text)
    parsed_input = parse_user_input(msg_text.strip())
    return ParsedUserMessage(raw_message=msg, parsed_input=parsed_input)


class TestCommandCallback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.callback = CommandCallback(self.registry)

    def test_get_command_completions(self):
        completions = CommandCallback.get_command_completions()
        self.assertIn("/queue", completions)
        self.assertIn("/help", completions)
        self.assertIn("/quit", completions)

    async def test_plain_message_returns_none(self):
        parsed = make_parsed("Hello world")
        result = await self.callback(parsed)
        self.assertIsNone(result)

    async def test_unknown_command_returns_none(self):
        parsed = make_parsed("/unknown")
        result = await self.callback(parsed)
        self.assertIsNone(result)

    async def test_queue_command(self):
        mock_agent_message = Mock()
        mock_agent_message.add_queued_message = Mock()
        self.registry.get_member_typechecked.return_value = mock_agent_message
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/queue Test message")
        result = await self.callback(parsed)

        self.assertFalse(result)
        mock_agent_message.add_queued_message.assert_called_once()
        queued_msg = mock_agent_message.add_queued_message.call_args[0][0]
        self.assertEqual(queued_msg.message, "Test message")

    async def test_queue_command_empty(self):
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/queue")
        result = await self.callback(parsed)

        self.assertFalse(result)

    async def test_quit_command(self):
        self.registry.send = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/quit")
        result = await self.callback(parsed)

        self.assertFalse(result)
        self.registry.send.assert_called_once_with("exit_signal", {"return_code": 0})

    async def test_exit_command(self):
        self.registry.send = AsyncMock()
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/exit")
        result = await self.callback(parsed)

        self.assertFalse(result)
        self.registry.send.assert_called_once_with("exit_signal", {"return_code": 0})

    async def test_help_command(self):
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/help")
        result = await self.callback(parsed)

        self.assertFalse(result)

    async def test_status_command(self):
        mock_agent = Mock()
        mock_agent.get_current_llm_info.return_value = ("test-llm", Mock())
        mock_agent.get_threshold_info.return_value = None
        mock_agent.state = "working"
        self.registry.get_member_typechecked.return_value = mock_agent
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("/status")
        result = await self.callback(parsed)

        self.assertFalse(result)
        mock_agent.get_current_llm_info.assert_called_once()

    async def test_switch_model(self):
        mock_agent = Mock()
        mock_llm_manager = Mock()
        mock_llm_manager.llm_names = ["test-llm", "another-llm"]
        mock_llm_manager.switch_to_llm = AsyncMock()
        mock_llm_manager.default_llm_name = "test-llm"
        mock_agent.llm_manager = mock_llm_manager
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked.return_value = mock_agent
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("@test-llm hello")
        result = await self.callback(parsed)

        self.assertTrue(result)
        mock_llm_manager.switch_to_llm.assert_called_once_with("test-llm")
        mock_agent.message_processor.add_new_message.assert_called_once()

    async def test_switch_model_invalid(self):
        mock_agent = Mock()
        mock_llm_manager = Mock()
        mock_llm_manager.llm_names = ["test-llm"]
        mock_agent.llm_manager = mock_llm_manager
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked.return_value = mock_agent
        self.registry.send_if_exists = AsyncMock()

        parsed = make_parsed("@invalid hello")
        result = await self.callback(parsed)

        self.assertTrue(result)
        mock_agent.message_processor.add_new_message.assert_called_once()


if __name__ == "__main__":
    asyncio.run(unittest.main())
