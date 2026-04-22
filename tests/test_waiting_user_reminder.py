import unittest
from unittest.mock import Mock

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import WAITING_USER_MARKER
from linhai.plugin.message_checkers import Plugin, WaitingUserReminderPlugin
from linhai.registry import Registry


class TestWaitingUserReminderPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Registry()
        self.lifecycle = Lifecycle(self.registry)
        self.plugin = WaitingUserReminderPlugin(self.registry)

        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

    def test_plugin_inherits_plugin(self):
        self.assertIsInstance(self.plugin, Plugin)

    def test_plugin_registers_both_hooks(self):
        before_count = len(self.lifecycle.before_message_generation._callbacks)
        after_count = len(self.lifecycle.after_message_generation._callbacks)
        self.plugin.register(self.lifecycle)
        self.assertEqual(
            len(self.lifecycle.before_message_generation._callbacks), before_count + 1
        )
        self.assertEqual(
            len(self.lifecycle.after_message_generation._callbacks), after_count + 1
        )

    async def test_reminder_shown_before_threshold(self):
        self.registry.register_member("agent", self.agent)

        for i in range(10):
            await self.plugin.before_message_generation()
            self.agent.message_processor.update_notification_message.assert_called()
            call_args = (
                self.agent.message_processor.update_notification_message.call_args
            )
            self.assertEqual(call_args.kwargs["source"], "waiting_user_reminder")
            self.assertIsNotNone(call_args.args[0])
            self.agent.message_processor.update_notification_message.reset_mock()
            await self.plugin.after_message_generation(None, f"msg {i}", [])

    async def test_reminder_removed_after_threshold(self):
        self.registry.register_member("agent", self.agent)

        for i in range(10):
            await self.plugin.before_message_generation()
            await self.plugin.after_message_generation(None, f"msg {i}", [])

        self.agent.message_processor.update_notification_message.reset_mock()
        await self.plugin.before_message_generation()
        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNone(call_args.args[0])
        self.assertEqual(call_args.kwargs["source"], "waiting_user_reminder")

    async def test_no_agent_skips(self):
        result = await self.plugin.before_message_generation()
        self.assertIsNone(result)

    async def test_reminder_contains_marker(self):
        self.registry.register_member("agent", self.agent)
        await self.plugin.before_message_generation()
        call_args = self.agent.message_processor.update_notification_message.call_args
        message_obj = call_args.args[0]
        self.assertIn(WAITING_USER_MARKER, message_obj.message)

    async def test_threshold_is_exactly_10(self):
        self.assertEqual(self.plugin.REMINDER_THRESHOLD, 10)

    async def test_counter_increments_each_message(self):
        for _ in range(15):
            await self.plugin.after_message_generation(None, "msg", [])
        self.assertEqual(self.plugin._message_count, 15)

    async def test_reminder_stays_removed(self):
        self.registry.register_member("agent", self.agent)

        for i in range(10):
            await self.plugin.before_message_generation()
            await self.plugin.after_message_generation(None, f"msg {i}", [])

        for _ in range(5):
            self.agent.message_processor.update_notification_message.reset_mock()
            await self.plugin.before_message_generation()
            call_args = (
                self.agent.message_processor.update_notification_message.call_args
            )
            self.assertIsNone(call_args.args[0])


if __name__ == "__main__":
    unittest.main()
