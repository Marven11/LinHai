import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from linhai.plugin.claw import ClawHeartbeatPlugin
from linhai.agent.base import RuntimeMessage
from linhai.registry import Registry


class TestClawHeartbeatPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = Registry()
        self.plugin = ClawHeartbeatPlugin(self.registry)

    def test_register(self):
        mock_lifecycle = Mock()
        self.plugin.register(mock_lifecycle)
        mock_lifecycle.register_before_waiting_user.assert_called_once_with(
            self.plugin.before_waiting_user
        )

    def test_heartbeat_creates_supervised_task(self):
        from linhai.task_supervisor import PlainTaskSupervisor

        ts = PlainTaskSupervisor()
        ts.create_supervised_task = Mock()
        mock_agent = Mock()
        mock_agent.state = "waiting_user"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        self.registry.register_member("task_supervisor", ts)

        async def run_test():
            await self.plugin.before_waiting_user(mock_agent)

        asyncio.run(run_test())

        ts.create_supervised_task.assert_called_once()
        call_args = ts.create_supervised_task.call_args
        self.assertEqual(call_args[0][0], "claw_heartbeat")

    def test_heartbeat_wakes_after_interval(self):
        mock_agent = Mock()
        mock_agent.state = "waiting_user"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", new_callable=AsyncMock):
                await self.plugin._heartbeat(mock_agent)

        asyncio.run(run_test())

        self.assertEqual(mock_agent.state, "working")
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args
        msg = call_args[0][0]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("十分钟过去了", msg.get_content())

    def test_heartbeat_skips_if_not_waiting(self):
        mock_agent = Mock()
        mock_agent.state = "working"
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", new_callable=AsyncMock):
                await self.plugin._heartbeat(mock_agent)

        asyncio.run(run_test())

        self.assertEqual(mock_agent.state, "working")
        mock_agent.message_processor.add_new_message.assert_not_called()

    def test_heartbeat_uses_correct_interval(self):
        self.assertEqual(ClawHeartbeatPlugin.HEARTBEAT_INTERVAL, 600)


class TestClawHeartbeatIntegration(unittest.TestCase):

    def test_heartbeat_sleeps_then_checks_state(self):
        registry = Registry()
        plugin = ClawHeartbeatPlugin(registry)
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()

        sleep_durations = []

        async def fake_sleep(duration):
            sleep_durations.append(duration)
            mock_agent.state = "waiting_user"

        async def run_test():
            with patch("linhai.plugin.claw.asyncio.sleep", side_effect=fake_sleep):
                await plugin._heartbeat(mock_agent)

        asyncio.run(run_test())

        self.assertEqual(sleep_durations, [600])
        self.assertEqual(mock_agent.state, "working")


if __name__ == "__main__":
    unittest.main()
