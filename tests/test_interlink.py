import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from linhai.agent.messages import RuntimeMessage
from linhai.agent.state_machine import AgentStateMachine
from linhai.plugin.interlink import InterlinkPlugin
from linhai.registry import Registry


class TestInterlinkPluginRegister(unittest.TestCase):

    def test_register_hooks(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        mock_lifecycle = Mock()
        plugin.register(mock_lifecycle)
        mock_lifecycle.before_agent_loop.register.assert_called_once_with(
            plugin.before_agent_loop
        )
        mock_lifecycle.before_message_generation.register.assert_called_once_with(
            plugin.before_message_generation
        )


class TestInterlinkPluginInit(unittest.TestCase):

    def test_agent_id_format(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        self.assertTrue(plugin.agent_id.startswith("@"))
        self.assertEqual(len(plugin.agent_id), 5)

    def test_file_path(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "my_channel")
        expected = (
            Path.home()
            / ".local"
            / "share"
            / "linhai"
            / "interlink"
            / "my_channel"
            / "INTERLINK.txt"
        )
        self.assertEqual(plugin.interlink_file, expected)


class TestInterlinkBeforeAgentLoop(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.interlink_dir = Path(self.temp_dir) / "interlink" / "test_channel"
        self.interlink_file = self.interlink_dir / "INTERLINK.txt"

    def test_creates_file_if_not_exists(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_dir = self.interlink_dir
        plugin.interlink_file = self.interlink_file

        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        mock_system_message = Mock()
        mock_ts = Mock()

        def get_member(name, t=None):
            if name == "system_message":
                return mock_system_message
            if name == "task_supervisor":
                return mock_ts
            return None

        registry.get_member_typechecked = get_member

        async def run_test():
            await plugin.before_agent_loop(mock_agent)

        asyncio.run(run_test())

        self.assertTrue(self.interlink_file.exists())
        mock_system_message.add_introduction.assert_called_once()
        mock_agent.message_processor.add_new_message.assert_called_once()
        msg = mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(msg, RuntimeMessage)
        content = msg.get_content()
        self.assertIn(str(self.interlink_file.resolve()), content)
        self.assertIn(plugin.agent_id, content)


class TestInterlinkBeforeMessageGeneration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.interlink_file = Path(self.temp_dir) / "INTERLINK.txt"

    def test_no_change_no_message(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        plugin._old_content = ""
        self.interlink_file.write_text("", encoding="utf-8")

        async def run_test():
            await plugin.before_message_generation()

        asyncio.run(run_test())

    def test_detects_new_content(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        plugin._old_content = ""
        self.interlink_file.write_text("@abcd hello from agent 1\n", encoding="utf-8")

        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        def get_member(name, t=None):
            if name == "agent":
                return mock_agent
            return None

        registry.get_member_typechecked = get_member
        registry.send_if_exists = AsyncMock()

        async def run_test():
            await plugin.before_message_generation()

        asyncio.run(run_test())

        mock_agent.message_processor.add_new_message.assert_called_once()
        msg = mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("hello from agent 1", msg.get_content())
        self.assertEqual(plugin._old_content, "@abcd hello from agent 1\n")

    def test_only_new_content_notified(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        plugin._old_content = "@abcd hello from agent 1\n"
        self.interlink_file.write_text(
            "@abcd hello from agent 1\n@ef56 reply from agent 2\n",
            encoding="utf-8",
        )

        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        def get_member(name, t=None):
            if name == "agent":
                return mock_agent
            return None

        registry.get_member_typechecked = get_member
        registry.send_if_exists = AsyncMock()

        async def run_test():
            await plugin.before_message_generation()

        asyncio.run(run_test())

        mock_agent.message_processor.add_new_message.assert_called_once()
        msg = mock_agent.message_processor.add_new_message.call_args[0][0]
        content = msg.get_content()
        self.assertIn("reply from agent 2", content)

    def test_no_duplicate_notification(self):
        registry = Registry()
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        self.interlink_file.write_text("@abcd msg\n", encoding="utf-8")
        plugin._old_content = "@abcd msg\n"

        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        def get_member(name, t=None):
            if name == "agent":
                return mock_agent
            return None

        registry.get_member_typechecked = get_member

        async def run_test():
            await plugin.before_message_generation()

        asyncio.run(run_test())

        mock_agent.message_processor.add_new_message.assert_not_called()


class TestInterlinkMonitorLoop(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.interlink_file = Path(self.temp_dir) / "INTERLINK.txt"
        self.interlink_file.write_text("", encoding="utf-8")

    def test_wakes_agent_on_change(self):
        registry = Registry()
        state_machine = AgentStateMachine(registry)
        state_machine.state = "waiting_user"
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        plugin._old_content = ""

        mock_agent = Mock()
        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                self.interlink_file.write_text("@abcd hello\n", encoding="utf-8")
            if call_count >= 2:
                raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.interlink.asyncio.sleep", side_effect=fake_sleep):
                await plugin._monitor_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        self.assertEqual(state_machine.state, "working")
        self.assertEqual(plugin._old_content, "")

    def test_no_wake_when_working(self):
        registry = Registry()
        state_machine = AgentStateMachine(registry)
        state_machine.state = "working"
        plugin = InterlinkPlugin(registry, "test_channel")
        plugin.interlink_file = self.interlink_file
        plugin._old_content = ""

        mock_agent = Mock()
        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                self.interlink_file.write_text("@abcd hello\n", encoding="utf-8")
            if call_count >= 2:
                raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.interlink.asyncio.sleep", side_effect=fake_sleep):
                await plugin._monitor_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        self.assertEqual(state_machine.state, "working")


if __name__ == "__main__":
    unittest.main()
