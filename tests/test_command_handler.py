"""Unit tests for the CommandHandler module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, MagicMock

from linhai.cli.command_handler import CommandHandler
from linhai.group_chat import GroupChat


class TestCommandHandler(unittest.IsolatedAsyncioTestCase):
    """Test cases for the CommandHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.group_chat = Mock(spec=GroupChat)
        self.handler = CommandHandler(self.group_chat)

    def test_init(self):
        """Test CommandHandler initialization."""
        self.assertEqual(self.handler.group_chat, self.group_chat)

    async def test_handle_command_empty(self):
        """Test handling empty input."""
        handled, should_interrupt = await self.handler.handle_command("")
        self.assertFalse(handled)
        self.assertFalse(should_interrupt)

    async def test_handle_command_not_a_command(self):
        """Test handling non-command input."""
        handled, should_interrupt = await self.handler.handle_command("Hello world")
        self.assertFalse(handled)
        self.assertFalse(should_interrupt)

    async def test_handle_queue_command(self):
        """Test /queue command."""
        mock_agent = Mock()
        mock_agent.queued_messages = []
        self.group_chat.get_member_typechecked.return_value = mock_agent

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        mock_messages_list = Mock()
        mock_messages_list.add_runtime_message = Mock()
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app,
            "messages_list": mock_messages_list,
        }[name]

        # Mock _show_success_message to ensure it's not called
        self.handler._show_success_message = AsyncMock()

        handled, should_interrupt = await self.handler.handle_command(
            "/queue Test message"
        )
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        self.assertEqual(len(mock_agent.queued_messages), 1)
        # Verify that no success message was shown (which would interrupt agent)
        self.handler._show_success_message.assert_not_called()
        # Verify the queued message content
        queued_msg = mock_agent.queued_messages[0]
        self.assertEqual(queued_msg.message, "Test message")
        # Verify that add_runtime_message was not called (no interrupt)
        mock_messages_list.add_runtime_message.assert_not_called()

    async def test_handle_quit_command(self):
        """Test /quit command."""
        self.group_chat.send = AsyncMock()

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "cli_app": mock_cli_app
        }[name]

        handled, should_interrupt = await self.handler.handle_command("/quit")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        self.group_chat.send.assert_called_once_with("exit_signal", {"return_code": 0})

    async def test_handle_exit_command(self):
        """Test /exit command."""
        self.group_chat.send = AsyncMock()

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "cli_app": mock_cli_app
        }[name]

        handled, should_interrupt = await self.handler.handle_command("/exit")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        self.group_chat.send.assert_called_once_with("exit_signal", {"return_code": 0})

    async def test_handle_help_command(self):
        """Test /help command."""
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_member_typechecked.return_value = mock_cli_app

        handled, should_interrupt = await self.handler.handle_command("/help")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)

    async def test_handle_status_command(self):
        """Test /status command."""
        mock_agent = Mock()
        mock_agent.get_current_llm_info.return_value = ("test-llm", Mock())
        mock_agent.get_threshold_info.return_value = None
        self.group_chat.get_member_typechecked.return_value = mock_agent

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        mock_messages_list = Mock()
        mock_messages_list.add_runtime_message = Mock()
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app,
            "messages_list": mock_messages_list,
        }[name]

        handled, should_interrupt = await self.handler.handle_command("/status")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        mock_agent.get_current_llm_info.assert_called_once()

    async def test_handle_unknown_command(self):
        """Test unknown command."""
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_member_typechecked.return_value = mock_cli_app

        handled, should_interrupt = await self.handler.handle_command("/unknown")
        self.assertFalse(handled)
        self.assertFalse(should_interrupt)

    async def test_handle_switch_model_command(self):
        """Test @model_name command."""
        mock_agent = Mock()
        mock_llm_manager = Mock()
        # 创建模拟LLM对象
        mock_llm1 = Mock()
        mock_llm1.get_name = Mock(return_value="test-llm")
        mock_llm2 = Mock()
        mock_llm2.get_name = Mock(return_value="another-llm")
        mock_llm_manager.llms = [mock_llm1, mock_llm2]
        mock_llm_manager.llm_names = ["test-llm", "another-llm"]
        mock_llm_manager.switch_to_llm = AsyncMock()
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm1)
        mock_llm_manager.default_llm_name = "test-llm"
        mock_agent.llm_manager = mock_llm_manager
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.get_member_typechecked.return_value = mock_agent

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        mock_messages_list = Mock()
        mock_messages_list.add_runtime_message = Mock()
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app,
            "messages_list": mock_messages_list,
        }[name]

        handled, should_interrupt = await self.handler.handle_command("@test-llm")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        mock_llm_manager.switch_to_llm.assert_called_once_with("test-llm")
        mock_agent.message_processor.add_new_message.assert_called_once()

    async def test_handle_switch_model_invalid(self):
        """Test @invalid_model_name command."""
        mock_agent = Mock()
        mock_llm_manager = Mock()
        # 创建模拟LLM对象
        mock_llm = Mock()
        mock_llm.get_name = Mock(return_value="test-llm")
        mock_llm_manager.llms = [mock_llm]
        mock_llm_manager.llm_names = ["test-llm"]
        mock_llm_manager.current_llm_index = 0
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        mock_agent.llm_manager = mock_llm_manager
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.get_member_typechecked.return_value = mock_agent

        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        mock_messages_list = Mock()
        mock_messages_list.add_runtime_message = Mock()
        self.group_chat.get_member_typechecked.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app,
            "messages_list": mock_messages_list,
        }[name]

        handled, should_interrupt = await self.handler.handle_command("@invalid")
        self.assertTrue(handled)
        self.assertFalse(should_interrupt)
        self.assertEqual(mock_agent.llm_manager.current_llm_index, 0)
        mock_agent.message_processor.add_new_message.assert_called_once()


if __name__ == "__main__":
    asyncio.run(unittest.main())
