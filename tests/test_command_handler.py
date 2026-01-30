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
        result = await self.handler.handle_command("")
        self.assertFalse(result)
        
    async def test_handle_command_not_a_command(self):
        """Test handling non-command input."""
        result = await self.handler.handle_command("Hello world")
        self.assertFalse(result)
        
    async def test_handle_todolist_list(self):
        """Test /todolist_list command."""
        # Mock the todolist manager
        mock_manager = Mock()
        mock_manager.list_todolists.return_value = []
        self.group_chat.get_members.return_value = mock_manager
        
        # Mock the CLI app for widget mounting
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "todolist_manager": mock_manager,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/todolist_list")
        self.assertTrue(result)
        mock_manager.list_todolists.assert_called_once()
        
    async def test_handle_todolist_add(self):
        """Test /todolist_add command."""
        mock_manager = Mock()
        mock_manager.add_todolist.return_value = "test-id"
        self.group_chat.get_members.return_value = mock_manager
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "todolist_manager": mock_manager,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/todolist_add Test task")
        self.assertTrue(result)
        mock_manager.add_todolist.assert_called_once_with("Test task")
        
    async def test_handle_todolist_add_no_args(self):
        """Test /todolist_add command with no arguments."""
        mock_manager = Mock()
        self.group_chat.get_members.return_value = mock_manager
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/todolist_add")
        self.assertTrue(result)
        mock_manager.add_todolist.assert_not_called()
        
    async def test_handle_queue_command(self):
        """Test /queue command."""
        mock_agent = Mock()
        mock_agent.queued_messages = []
        self.group_chat.get_members.return_value = mock_agent
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/queue Test message")
        self.assertTrue(result)
        self.assertEqual(len(mock_agent.queued_messages), 1)
        
    async def test_handle_quit_command(self):
        """Test /quit command."""
        self.group_chat.send = AsyncMock()
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/quit")
        self.assertTrue(result)
        self.group_chat.send.assert_called_once_with("exit_signal", {"return_code": 0})
        
    async def test_handle_exit_command(self):
        """Test /exit command."""
        self.group_chat.send = AsyncMock()
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/exit")
        self.assertTrue(result)
        self.group_chat.send.assert_called_once_with("exit_signal", {"return_code": 0})
        
    async def test_handle_help_command(self):
        """Test /help command."""
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.return_value = mock_cli_app
        
        result = await self.handler.handle_command("/help")
        self.assertTrue(result)
        
    async def test_handle_status_command(self):
        """Test /status command."""
        mock_agent = Mock()
        mock_agent.get_current_llm_info.return_value = ("test-llm", Mock())
        mock_agent.get_threshold_info.return_value = None
        self.group_chat.get_members.return_value = mock_agent
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("/status")
        self.assertTrue(result)
        mock_agent.get_current_llm_info.assert_called_once()
        
    async def test_handle_unknown_command(self):
        """Test unknown command."""
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.return_value = mock_cli_app
        
        result = await self.handler.handle_command("/unknown")
        self.assertFalse(result)
        
    async def test_handle_switch_model_command(self):
        """Test @model_name command."""
        mock_agent = Mock()
        mock_agent.llm_names = ["test-llm", "another-llm"]
        mock_agent.current_llm_index = 0
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = Mock()
        self.group_chat.get_members.return_value = mock_agent
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("@test-llm")
        self.assertTrue(result)
        self.assertEqual(mock_agent.current_llm_index, 0)
        
    async def test_handle_switch_model_invalid(self):
        """Test @invalid_model_name command."""
        mock_agent = Mock()
        mock_agent.llm_names = ["test-llm"]
        mock_agent.current_llm_index = 0
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = Mock()
        self.group_chat.get_members.return_value = mock_agent
        
        mock_cli_app = Mock()
        mock_container = Mock()
        mock_cli_app.query_one.return_value = mock_container
        mock_cli_app.should_auto_scroll.return_value = True
        self.group_chat.get_members.side_effect = lambda name, cls: {
            "agent": mock_agent,
            "cli_app": mock_cli_app
        }[name]
        
        result = await self.handler.handle_command("@invalid")
        self.assertTrue(result)
        self.assertEqual(mock_agent.current_llm_index, 0)


if __name__ == "__main__":
    asyncio.run(unittest.main())