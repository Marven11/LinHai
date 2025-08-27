"""Unit tests for agent plugins."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent_plugin import WaitingUserPlugin, MarkerValidationPlugin
from linhai.agent_base import WAITING_USER_MARKER, RuntimeMessage


class TestWaitingUserPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for WaitingUserPlugin."""

    def setUp(self):
        self.plugin = WaitingUserPlugin()
        self.agent = MagicMock()
        self.agent.messages = []
        self.agent.state = "working"

    async def test_marker_in_last_line(self):
        """Test when WAITING_USER_MARKER is in the last line."""
        full_response = f"Some response\n{WAITING_USER_MARKER}"
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, []
        )
        
        self.assertEqual(len(self.agent.messages), 0)
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_marker_not_in_last_line(self):
        """Test when WAITING_USER_MARKER is not in the last line."""
        full_response = f"{WAITING_USER_MARKER}\nSome other content"
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, []
        )
        
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
        self.assertIn("不在最后一行", self.agent.messages[0].message)
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_register_plugin(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


class TestMarkerValidationPlugin(unittest.IsolatedAsyncioTestCase):
    """Test cases for MarkerValidationPlugin."""

    def setUp(self):
        self.plugin = MarkerValidationPlugin()
        self.agent = MagicMock()
        self.agent.messages = []
        self.agent.state = "working"
        self.agent.current_disable_waiting_user_warning = False

    async def test_both_tool_calls_and_marker(self):
        """Test when both tool calls and marker are present."""
        full_response = f"Some response with {WAITING_USER_MARKER}"
        tool_calls = [{"name": "test_tool", "arguments": "{}"}]
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, tool_calls
        )
        
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
        self.assertIn("既调用了工具又使用了", self.agent.messages[0].message)

    async def test_no_tool_calls_no_marker(self):
        """Test when no tool calls and no marker in working state."""
        full_response = "Some response without marker"
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, []
        )
        
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
        self.assertIn("警告", self.agent.messages[0].message)
        self.assertIn("等待用户回答", self.agent.messages[0].message)

    async def test_only_tool_calls(self):
        """Test when only tool calls are present."""
        full_response = "Some response with tool calls"
        tool_calls = [{"name": "test_tool", "arguments": "{}"}]
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, tool_calls
        )
        
        self.assertEqual(len(self.agent.messages), 0)

    async def test_only_marker(self):
        """Test when only marker is present."""
        full_response = f"Some response with {WAITING_USER_MARKER}"
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, []
        )
        
        # Agent state is "working" and no tool calls, so warning message should be added
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
        self.assertIn("警告", self.agent.messages[0].message)

    async def test_disable_warning_flag(self):
        """Test when warning is disabled."""
        self.agent.current_disable_waiting_user_warning = True
        full_response = f"Some response with {WAITING_USER_MARKER}"
        tool_calls = [{"name": "test_tool", "arguments": "{}"}]
        
        await self.plugin.after_message_generation(
            self.agent, None, full_response, tool_calls
        )
        
        self.assertEqual(len(self.agent.messages), 0)

    async def test_register_plugin(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()