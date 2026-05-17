import asyncio
import time
import unittest
from unittest.mock import Mock, AsyncMock, patch

from linhai.plugin.claw import ClawHeartbeatPlugin
from linhai.agent.messages import RuntimeMessage
from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry


class TestClawHeartbeatPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = Registry()
        self.state_machine = AgentStateMachine(self.registry)
        self.plugin = ClawHeartbeatPlugin(self.registry, 1800)

    def test_register(self):
        mock_lifecycle = Mock()
        self.plugin.register(mock_lifecycle)
        mock_lifecycle.before_agent_loop.register.assert_called_once_with(
            self.plugin.before_agent_loop
        )
        mock_lifecycle.before_message_generation.register.assert_called_once_with(
            self.plugin.before_message_generation
        )

    def test_before_agent_loop_creates_supervised_task(self):
        from linhai.task_supervisor import PlainTaskSupervisor

        ts = PlainTaskSupervisor()
        ts.create_supervised_task = Mock()
        mock_agent = Mock()
        self.registry.register_member("task_supervisor", ts)

        async def run_test():
            await self.plugin.before_agent_loop(mock_agent)

        asyncio.run(run_test())

        ts.create_supervised_task.assert_called_once()
        call_args = ts.create_supervised_task.call_args
        self.assertEqual(call_args[0][0], "claw_heartbeat")

    def test_before_message_generation_resets_timer(self):
        original_time = self.plugin._next_reminder_time

        async def run_test():
            await self.plugin.before_message_generation()

        asyncio.run(run_test())

        self.assertGreater(self.plugin._next_reminder_time, original_time)

    def test_heartbeat_loop_wakes_after_interval(self):
        mock_agent = Mock()
        self.state_machine.state = "waiting_user"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            self.plugin._next_reminder_time = time.monotonic() - 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", side_effect=fake_sleep):
                await self.plugin._heartbeat_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        self.assertEqual(self.state_machine.state, "working")
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        msg = call_args[0][0]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("30分钟过去了", msg.get_content())

    def test_heartbeat_loop_skips_if_not_waiting(self):
        mock_agent = Mock()
        self.state_machine.state = "working"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", side_effect=fake_sleep):
                await self.plugin._heartbeat_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        mock_agent.message_processor.add_new_message.assert_not_called()

    def test_heartbeat_uses_correct_interval(self):
        plugin = ClawHeartbeatPlugin(self.registry, 1800)
        self.assertEqual(plugin.heartbeat_interval, 1800)

    def test_heartbeat_loop_sleeps_remaining_time(self):
        registry = Registry()
        state_machine = AgentStateMachine(registry)
        plugin = ClawHeartbeatPlugin(registry, 1800)
        plugin._next_reminder_time = time.monotonic() + 1800
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        sleep_durations = []

        async def fake_sleep(duration):
            sleep_durations.append(duration)
            state_machine.state = "waiting_user"
            raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", side_effect=fake_sleep):
                await plugin._heartbeat_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        self.assertEqual(len(sleep_durations), 1)
        self.assertAlmostEqual(sleep_durations[0], 1800, delta=1)

    def test_timer_reset_during_sleep_prevents_reminder(self):
        registry = Registry()
        state_machine = AgentStateMachine(registry)
        plugin = ClawHeartbeatPlugin(registry, 1800)
        plugin._next_reminder_time = time.monotonic() + 1800
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        sleep_count = 0

        async def fake_sleep(duration):
            nonlocal sleep_count
            sleep_count += 1
            plugin._next_reminder_time = time.monotonic() + 1800
            if sleep_count >= 3:
                raise asyncio.CancelledError()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", side_effect=fake_sleep):
                await plugin._heartbeat_loop(mock_agent)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        mock_agent.message_processor.add_new_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
