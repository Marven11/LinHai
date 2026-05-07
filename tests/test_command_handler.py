import argparse
import asyncio
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

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

    async def test_save_command_uses_saved_json(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            conversation_folder = Path(tmpdir)
            self.registry.get_member_typechecked.return_value = conversation_folder
            self.registry.send_if_exists = AsyncMock()

            with patch(
                "linhai.agent.conversation_save.save_conversation",
                new_callable=AsyncMock,
            ) as mock_save:
                parsed = make_parsed("/save")
                result = await self.callback(parsed)

                self.assertFalse(result)
                expected_path = conversation_folder / "saved.json"
                mock_save.assert_called_once_with(self.registry, expected_path)

    async def test_save_command_no_saves_subdirectory(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            conversation_folder = Path(tmpdir)
            self.registry.get_member_typechecked.return_value = conversation_folder
            self.registry.send_if_exists = AsyncMock()

            with patch(
                "linhai.agent.conversation_save.save_conversation",
                new_callable=AsyncMock,
            ):
                parsed = make_parsed("/save")
                await self.callback(parsed)

                self.assertFalse((conversation_folder / "saves").exists())


class TestRestoreConversationCli(unittest.TestCase):
    def test_restore_conversation_resolves_path(self):
        from linhai.main import main
        import sys

        with patch("sys.argv", ["linhai", "--restore-conversation", "test-uuid-123"]):
            with patch("linhai.main.run") as mock_run:
                with patch(
                    "linhai.main.get_default_config_path",
                    return_value=Path("/fake/config"),
                ):
                    mock_run.return_value = 0
                    with patch("sys.exit"):
                        main()

        call_args = mock_run.call_args[0][0]
        expected = (
            Path.home()
            / ".local"
            / "share"
            / "linhai"
            / "conversation"
            / "test-uuid-123"
            / "saved.json"
        )
        self.assertEqual(call_args.restore_conversation, "test-uuid-123")

    def test_restore_conversation_none_by_default(self):
        from linhai.main import main

        with patch("sys.argv", ["linhai"]):
            with patch("linhai.main.run") as mock_run:
                with patch(
                    "linhai.main.get_default_config_path",
                    return_value=Path("/fake/config"),
                ):
                    mock_run.return_value = 0
                    with patch("sys.exit"):
                        main()

        call_args = mock_run.call_args[0][0]
        self.assertIsNone(call_args.restore_conversation)


if __name__ == "__main__":
    asyncio.run(unittest.main())
