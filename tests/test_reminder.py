from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock
from linhai.group_chat import GroupChat
from linhai.plugin.reminder import ReminderPlugin
from linhai.plugin.message_checkers import Plugin
from linhai.agent.lifecycle import Lifecycle


class TestReminderPlugin(TestCase):
    def setUp(self):
        self.group_chat = GroupChat()
        self.lifecycle = Lifecycle(self.group_chat)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.claw_dir = Path(self.temp_dir.name)
        self.reminder_file = self.claw_dir / "REMINDER.md"
        self.plugin = ReminderPlugin(self.group_chat, self.claw_dir)

        # 创建模拟的Agent
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

        # 注册到group chat
        self.group_chat.register_member("agent", self.agent)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plugin_inherits_plugin(self):
        self.assertIsInstance(self.plugin, Plugin)

    def test_plugin_registers_before_message_generation(self):
        initial_count = len(self.lifecycle._before_message_generation_callbacks)
        self.plugin.register(self.lifecycle)
        self.assertEqual(
            len(self.lifecycle._before_message_generation_callbacks), initial_count + 1
        )
