from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock
from linhai.registry import Registry
from linhai.plugin.reminder import ReminderPlugin
from linhai.plugin.message_checkers import Plugin
from linhai.agent.lifecycle import Lifecycle


class TestReminderPlugin(TestCase):
    def setUp(self):
        self.registry = Registry()
        self.lifecycle = Lifecycle(self.registry)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.claw_dir = Path(self.temp_dir.name)
        self.reminder_file = self.claw_dir / "REMINDER.md"
        self.soul_file = self.claw_dir / "SOUL.md"
        self.plugin = ReminderPlugin(self.registry, self.claw_dir)

        # 创建模拟的Agent
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

        # 注册到group chat
        self.registry.register_member("agent", self.agent)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plugin_inherits_plugin(self):
        self.assertIsInstance(self.plugin, Plugin)

    def test_plugin_registers_before_message_generation(self):
        initial_count = len(self.lifecycle.before_message_generation._callbacks)
        self.plugin.register(self.lifecycle)
        self.assertEqual(
            len(self.lifecycle.before_message_generation._callbacks), initial_count + 1
        )

    def test_soul_file_is_tracked(self):
        """测试SOUL.md文件路径被正确设置"""
        self.assertEqual(self.plugin.soul_file, self.soul_file)

    def test_reminder_file_is_tracked(self):
        """测试REMINDER.md文件路径被正确设置"""
        self.assertEqual(self.plugin.reminder_file, self.reminder_file)
