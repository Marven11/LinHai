"""Unit tests for agent plugins."""

import unittest
from unittest.mock import MagicMock

from linhai.agent_plugin import WaitingUserPlugin
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

        await self.plugin.after_message_generation(self.agent, None, full_response, [])

        self.assertEqual(len(self.agent.messages), 0)
        self.assertEqual(self.agent.state, "waiting_user")

    async def test_marker_not_in_last_line(self):
        """Test when WAITING_USER_MARKER is not in the last line."""
        full_response = f"{WAITING_USER_MARKER}\nSome other content"

        await self.plugin.after_message_generation(self.agent, None, full_response, [])

        self.assertEqual(len(self.agent.messages), 1)
        self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
        self.assertIn("不在最后一行", self.agent.messages[0].message)
        self.assertEqual(self.agent.state, "working")  # 状态应为working，因为标记不在最后一行

    async def test_register_plugin(self):
        """Test plugin registration."""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )


if __name__ == "__main__":
    unittest.main()
