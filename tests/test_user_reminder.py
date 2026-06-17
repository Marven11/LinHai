from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from linhai.agent.lifecycle import Lifecycle
from linhai.plugin.message_checkers import Plugin
from linhai.plugin.user_reminder import UserReminderPlugin
from linhai.registry import Registry


class TestUserReminderPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Registry()
        self.lifecycle = Lifecycle(self.registry)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reminder_file = Path(self.temp_dir.name) / "REMINDER.md"
        self.plugin = UserReminderPlugin(self.registry, str(self.reminder_file))

        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_nonexistent_file_skips(self):
        self.plugin = UserReminderPlugin(self.registry, "/nonexistent/path/reminder.md")
        result = await self.plugin.before_message_generation()
        self.assertIsNone(result)

    async def test_empty_file_skips(self):
        self.reminder_file.write_text("", encoding="utf-8")
        result = await self.plugin.before_message_generation()
        self.assertIsNone(result)

    async def test_no_agent_skips(self):
        self.reminder_file.write_text("test content", encoding="utf-8")
        result = await self.plugin.before_message_generation()
        self.assertIsNone(result)

    async def test_reminder_content_added_to_notification(self):
        self.reminder_file.write_text("test reminder content", encoding="utf-8")
        self.registry.register_member("agent", self.agent)

        await self.plugin.before_message_generation()

        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertEqual(call_args.kwargs["source"], "user_reminder")
        message_obj = call_args.args[0]
        self.assertIn("test reminder content", str(message_obj))

    async def test_relative_path_with_config_path(self):
        config_file = Path(self.temp_dir.name) / "config.toml"
        config_file.write_text("", encoding="utf-8")
        self.registry.register_member("config_path", str(config_file))
        self.registry.register_member("agent", self.agent)

        relative_path = "reminder.md"
        reminder_file = Path(self.temp_dir.name) / "reminder.md"
        reminder_file.write_text("relative reminder", encoding="utf-8")

        plugin = UserReminderPlugin(self.registry, relative_path)
        await plugin.before_message_generation()

        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIn("relative reminder", str(call_args.args[0]))

    async def test_absolute_path_works(self):
        self.reminder_file.write_text("absolute path reminder", encoding="utf-8")
        self.registry.register_member("agent", self.agent)

        plugin = UserReminderPlugin(self.registry, str(self.reminder_file))
        await plugin.before_message_generation()

        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIn("absolute path reminder", str(call_args.args[0]))

    async def test_tilde_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / ".test_reminder.md"
            test_file.write_text("home reminder", encoding="utf-8")
            self.registry.register_member("agent", self.agent)

            with patch.object(Path, "expanduser", return_value=test_file):
                plugin = UserReminderPlugin(self.registry, "~/.test_reminder.md")
                await plugin.before_message_generation()

                self.agent.message_processor.update_notification_message.assert_called_once()
                call_args = (
                    self.agent.message_processor.update_notification_message.call_args
                )
                self.assertIn("home reminder", str(call_args.args[0]))

    async def test_whitespace_only_content_skips(self):
        self.reminder_file.write_text("   \n\t   ", encoding="utf-8")
        self.registry.register_member("agent", self.agent)

        result = await self.plugin.before_message_generation()
        self.assertIsNone(result)
        self.agent.message_processor.update_notification_message.assert_not_called()

    async def test_multiple_calls_override_previous_notification(self):
        self.registry.register_member("agent", self.agent)
        self.reminder_file.write_text("第一次提醒", encoding="utf-8")
        await self.plugin.before_message_generation()
        self.agent.message_processor.update_notification_message.assert_called()
        first_call_msg = (
            self.agent.message_processor.update_notification_message.call_args[0][0]
        )
        self.assertIn("第一次提醒", first_call_msg.message)

        self.agent.message_processor.update_notification_message.reset_mock()
        self.reminder_file.write_text("第二次提醒", encoding="utf-8")
        await self.plugin.before_message_generation()
        self.agent.message_processor.update_notification_message.assert_called()
        second_call_msg = (
            self.agent.message_processor.update_notification_message.call_args[0][0]
        )
        self.assertIn("第二次提醒", second_call_msg.message)


if __name__ == "__main__":
    unittest.main()
