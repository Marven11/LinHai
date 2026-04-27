import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from linhai.plugin.system_message_leaning import CurrentDirectoryPlugin
from linhai.registry import Registry


class TestCurrentDirectoryPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.plugin = CurrentDirectoryPlugin(self.registry)

    def test_initialization(self):
        self.assertFalse(self.plugin._has_added)

    async def test_before_agent_loop_adds_pinned_message(self):
        mock_agent = MagicMock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        with patch("os.getcwd", return_value="/test/dir"):
            await self.plugin._before_agent_loop(mock_agent)

        self.assertTrue(self.plugin._has_added)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        runtime_msg = call_args[0][0]
        self.assertIn("当前目录为", runtime_msg.get_content())
        self.assertIn("/test/dir", runtime_msg.get_content())

    async def test_before_agent_loop_only_once(self):
        mock_agent = MagicMock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        with patch("os.getcwd", return_value="/test/dir"):
            await self.plugin._before_agent_loop(mock_agent)
            await self.plugin._before_agent_loop(mock_agent)

        mock_agent.message_processor.add_new_message.assert_called_once()

    def test_register_method(self):
        mock_lifecycle = Mock()
        self.plugin.register(mock_lifecycle)

        mock_lifecycle.before_agent_loop.register.assert_called_once_with(
            self.plugin._before_agent_loop
        )
