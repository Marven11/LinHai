from pathlib import Path
import tempfile
import unittest
from unittest import TestCase
from unittest.mock import Mock

from linhai.agent.lifecycle import Lifecycle
from linhai.plugin.message_checkers import Plugin
from linhai.plugin.reminder import ReminderPlugin, ReminderWriteGuardPlugin
from linhai.registry import Registry
from linhai.tool.base import FailedToolResult


class TestReminderPlugin(TestCase):
    def setUp(self):
        self.registry = Registry()
        self.lifecycle = Lifecycle(self.registry)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.claw_dir = Path(self.temp_dir.name)
        self.reminder_file = self.claw_dir / "REMINDER.md"
        self.soul_file = self.claw_dir / "SOUL.md"
        self.plugin = ReminderPlugin(self.registry, self.claw_dir)

        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

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
        self.assertEqual(self.plugin.soul_file, self.soul_file)

    def test_reminder_file_is_tracked(self):
        self.assertEqual(self.plugin.reminder_file, self.reminder_file)


class TestReminderWriteGuardPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.lifecycle = Lifecycle(self.registry)
        self.temp_dir = tempfile.mkdtemp()
        self.claw_dir = Path(self.temp_dir)
        self.reminder_file = self.claw_dir / "REMINDER.md"
        self.plugin = ReminderWriteGuardPlugin(self.registry, self.claw_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_plugin_inherits_plugin(self):
        self.assertIsInstance(self.plugin, Plugin)

    def test_register_adds_before_tool_call_callback(self):
        initial_count = len(self.lifecycle.before_tool_call._callbacks)
        self.plugin.register(self.lifecycle)
        self.assertEqual(
            len(self.lifecycle.before_tool_call._callbacks), initial_count + 1
        )

    async def test_write_file_short_single_line_allowed(self):
        self.reminder_file.write_text("short content", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "write_file",
            {"filepath": str(self.reminder_file), "content": "new short"},
            None,
        )
        self.assertIsNone(result)

    async def test_write_file_with_newline_blocked(self):
        result = await self.plugin.before_tool_call(
            "write_file",
            {
                "filepath": str(self.reminder_file),
                "content": "line1\nline2",
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("换行符", result.content)

    async def test_write_file_too_long_blocked(self):
        result = await self.plugin.before_tool_call(
            "write_file",
            {
                "filepath": str(self.reminder_file),
                "content": "a" * 101,
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("101字符", result.content)

    async def test_write_file_exactly_100_chars_allowed(self):
        result = await self.plugin.before_tool_call(
            "write_file",
            {
                "filepath": str(self.reminder_file),
                "content": "a" * 100,
            },
            None,
        )
        self.assertIsNone(result)

    async def test_write_file_trailing_newline_stripped(self):
        result = await self.plugin.before_tool_call(
            "write_file",
            {
                "filepath": str(self.reminder_file),
                "content": "short" + "\n",
            },
            None,
        )
        self.assertIsNone(result)

    async def test_write_file_other_path_not_blocked(self):
        other_file = self.claw_dir / "OTHER.md"
        result = await self.plugin.before_tool_call(
            "write_file",
            {"filepath": str(other_file), "content": "a" * 200},
            None,
        )
        self.assertIsNone(result)

    async def test_replace_file_content_newline_in_new_blocked(self):
        self.reminder_file.write_text("old text", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "old",
                "new": "new\nline",
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("换行符", result.content)

    async def test_replace_file_content_result_too_long_blocked(self):
        self.reminder_file.write_text("prefix old suffix", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "old",
                "new": "a" * 101,
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("过长", result.content)

    async def test_replace_file_content_short_replacement_allowed(self):
        self.reminder_file.write_text("short msg", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "short",
                "new": "tiny",
            },
            None,
        )
        self.assertIsNone(result)

    async def test_replace_file_content_nonexistent_file_allowed(self):
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "old",
                "new": "new",
            },
            None,
        )
        self.assertIsNone(result)

    async def test_replace_file_content_other_path_not_blocked(self):
        other_file = self.claw_dir / "OTHER.md"
        other_file.write_text("content", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(other_file),
                "old": "content",
                "new": "a" * 200,
            },
            None,
        )
        self.assertIsNone(result)

    async def test_other_tool_name_not_blocked(self):
        result = await self.plugin.before_tool_call(
            "read_file",
            {"filepath": str(self.reminder_file)},
            None,
        )
        self.assertIsNone(result)

    async def test_replace_file_content_replace_times_minus_one(self):
        self.reminder_file.write_text("abc abc abc", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "abc",
                "new": "x" * 40,
                "replace_times": -1,
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)

    async def test_replace_file_content_replace_times_positive(self):
        self.reminder_file.write_text("abc abc", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "abc",
                "new": "x" * 60,
                "replace_times": 2,
            },
            None,
        )
        self.assertIsInstance(result, FailedToolResult)

    async def test_replace_file_content_ambiguous_old_returns_none(self):
        self.reminder_file.write_text("abc abc", encoding="utf-8")
        result = await self.plugin.before_tool_call(
            "replace_file_content",
            {
                "filepath": str(self.reminder_file),
                "old": "abc",
                "new": "short",
            },
            None,
        )
        self.assertIsNone(result)
