import unittest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry


def _create_sm() -> AgentStateMachine:
    registry = MagicMock(spec=Registry)
    registry.register_member = MagicMock()
    registry.get_member_typechecked = MagicMock(
        return_value=MagicMock(
            has_message=MagicMock(return_value=False),
            receive_and_dispatch=AsyncMock(return_value=False),
        )
    )
    return AgentStateMachine(registry)


class TestAgentStateMachineInitial(unittest.TestCase):
    def test_initial_state_is_waiting_user(self):
        sm = _create_sm()
        self.assertEqual(sm.state, "waiting_user")

    def test_initial_sleeping_fields_are_none(self):
        sm = _create_sm()
        self.assertIsNone(sm.sleeping_since)
        self.assertIsNone(sm.sleeping_deadline)


class TestTransitionToWorking(unittest.TestCase):
    def test_from_waiting_user(self):
        sm = _create_sm()
        sm.transition_to_working()
        self.assertEqual(sm.state, "working")

    def test_from_working_is_idempotent(self):
        sm = _create_sm()
        sm.state = "working"
        sm.transition_to_working()
        self.assertEqual(sm.state, "working")

    def test_does_not_clear_sleep_fields_from_non_sleeping(self):
        sm = _create_sm()
        sm.sleeping_since = datetime.now()
        sm.sleeping_deadline = datetime.now() + timedelta(seconds=10)
        sm.transition_to_working()
        self.assertIsNotNone(sm.sleeping_since)
        self.assertIsNotNone(sm.sleeping_deadline)


class TestTransitionToSleeping(unittest.TestCase):
    def test_sets_state_and_fields(self):
        sm = _create_sm()
        now = datetime.now()
        deadline = now + timedelta(seconds=30)
        sm.transition_to_sleeping(now, deadline)
        self.assertEqual(sm.state, "sleeping")
        self.assertEqual(sm.sleeping_since, now)
        self.assertEqual(sm.sleeping_deadline, deadline)

    def test_overwrites_previous_sleep(self):
        sm = _create_sm()
        first = datetime.now()
        sm.transition_to_sleeping(first, first + timedelta(seconds=10))
        second = datetime.now()
        sm.transition_to_sleeping(second, second + timedelta(seconds=20))
        self.assertEqual(sm.sleeping_since, second)


class TestTransitionToWaitingUser(unittest.TestCase):
    def test_from_working(self):
        sm = _create_sm()
        sm.state = "working"
        sm.transition_to_waiting_user()
        self.assertEqual(sm.state, "waiting_user")

    def test_from_sleeping_does_not_clear_sleep_fields(self):
        sm = _create_sm()
        now = datetime.now()
        sm.transition_to_sleeping(now, now + timedelta(seconds=10))
        sm.transition_to_waiting_user()
        self.assertEqual(sm.state, "waiting_user")
        self.assertIsNotNone(sm.sleeping_since)


class TestInterruptToWorking(unittest.TestCase):
    def test_from_sleeping_clears_fields(self):
        sm = _create_sm()
        sm.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=100)
        )
        sm.interrupt_to_working()
        self.assertEqual(sm.state, "working")
        self.assertIsNone(sm.sleeping_since)
        self.assertIsNone(sm.sleeping_deadline)

    def test_from_waiting_user(self):
        sm = _create_sm()
        sm.interrupt_to_working()
        self.assertEqual(sm.state, "working")

    def test_from_working_is_idempotent(self):
        sm = _create_sm()
        sm.state = "working"
        sm.interrupt_to_working()
        self.assertEqual(sm.state, "working")


class TestFinishSleeping(unittest.TestCase):
    def test_clears_fields_and_transitions(self):
        sm = _create_sm()
        sm.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=10)
        )
        sm.finish_sleeping()
        self.assertEqual(sm.state, "working")
        self.assertIsNone(sm.sleeping_since)
        self.assertIsNone(sm.sleeping_deadline)

    def test_from_non_sleeping_also_works(self):
        sm = _create_sm()
        sm.sleeping_since = datetime.now()
        sm.sleeping_deadline = datetime.now()
        sm.finish_sleeping()
        self.assertEqual(sm.state, "working")
        self.assertIsNone(sm.sleeping_since)


class TestGenerateSleepToolset(unittest.IsolatedAsyncioTestCase):
    async def test_sleep_tool_waits_then_returns_working(self):
        sm = _create_sm()
        toolset = sm.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        self.assertEqual(sm.state, "waiting_user")

        result = await sleep_fn(seconds=0.1)

        self.assertEqual(sm.state, "working")
        self.assertIsNone(sm.sleeping_since)
        self.assertIsNone(sm.sleeping_deadline)

        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)
        self.assertIn("睡眠完成", result.content)


if __name__ == "__main__":
    unittest.main()
