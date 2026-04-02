import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.main import Agent
from linhai.llm_manager import LlmManager
from linhai.registry import Registry


def _create_agent() -> Agent:
    registry = MagicMock(spec=Registry)
    registry.is_empty = MagicMock(return_value=True)
    registry.receive = AsyncMock()
    registry.send = AsyncMock()
    registry.register_queue = MagicMock()
    registry.register_member = MagicMock()
    registry.send_if_exists = AsyncMock()

    mock_llm = MagicMock()
    mock_llm.get_name = MagicMock(return_value="test-llm")
    llm_manager = LlmManager(
        registry=registry,
        llms=[mock_llm],
        default_llm_name="test-llm",
        llm_fallback_map={"test-llm": None},
    )

    agent = Agent(
        llm_manager=llm_manager,
        compress_threshold=800,
        registry=registry,
        pinned_messages=[],
    )
    agent.registry = registry
    registry.get_member_typechecked = MagicMock(return_value=agent)
    return agent


class TestSleepTool(unittest.IsolatedAsyncioTestCase):
    async def test_sleep_tool_sets_state_and_fields(self):
        agent = _create_agent()
        toolset = agent.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        self.assertEqual(agent.state, "waiting_user")
        self.assertIsNone(agent.sleeping_since)
        self.assertIsNone(agent.sleeping_deadline)

        result = await sleep_fn(seconds=5.0)

        self.assertEqual(agent.state, "sleeping")
        self.assertIsNotNone(agent.sleeping_since)
        self.assertIsNotNone(agent.sleeping_deadline)

        expected_deadline = agent.sleeping_since + timedelta(seconds=5.0)
        self.assertAlmostEqual(
            (agent.sleeping_deadline - expected_deadline).total_seconds(),
            0.0,
            places=1,
        )

        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)


class TestStateSleeping(unittest.IsolatedAsyncioTestCase):
    async def test_state_sleeping_completes(self):
        agent = _create_agent()
        agent.sleeping_since = datetime.now()
        agent.sleeping_deadline = datetime.now() + timedelta(seconds=0.1)
        agent.state = "sleeping"

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        await agent.state_sleeping()

        self.assertEqual(agent.state, "working")
        self.assertIsNone(agent.sleeping_since)
        self.assertIsNone(agent.sleeping_deadline)
        agent.message_processor.add_new_message.assert_called_once()

    async def test_state_sleeping_interrupted_by_state_change(self):
        agent = _create_agent()
        agent.sleeping_since = datetime.now()
        agent.sleeping_deadline = datetime.now() + timedelta(seconds=10)
        agent.state = "sleeping"

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        call_count = 0

        def is_empty_side_effect(queue_name):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                agent.state = "working"
            return True

        agent.registry.is_empty = MagicMock(side_effect=is_empty_side_effect)

        await agent.state_sleeping()

        self.assertEqual(agent.state, "working")
        self.assertIsNone(agent.sleeping_since)
        self.assertIsNone(agent.sleeping_deadline)

    async def test_run_handles_sleeping_state(self):
        agent = _create_agent()
        agent.state = "sleeping"
        agent.sleeping_since = datetime.now()
        agent.sleeping_deadline = datetime.now() + timedelta(seconds=0.1)

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        call_count = 0

        async def fake_state_sleeping():
            nonlocal call_count
            call_count += 1
            agent.sleeping_since = None
            agent.sleeping_deadline = None
            agent.state = "waiting_user"

        agent.state_sleeping = fake_state_sleeping

        agent.state_waiting_user = AsyncMock()
        agent.state_working = AsyncMock()

        async def fake_state_waiting_user():
            agent.state = "__exit__"

        agent.state_waiting_user = fake_state_waiting_user

        await agent.run()

        self.assertEqual(call_count, 1)


class TestInterruptToWorking(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_from_sleeping(self):
        agent = _create_agent()
        agent.state = "sleeping"
        agent.sleeping_since = datetime.now()
        agent.sleeping_deadline = datetime.now() + timedelta(seconds=100)

        agent.interrupt_to_working()

        self.assertEqual(agent.state, "working")
        self.assertIsNone(agent.sleeping_since)
        self.assertIsNone(agent.sleeping_deadline)

    async def test_interrupt_from_waiting_user(self):
        agent = _create_agent()
        agent.state = "waiting_user"

        agent.interrupt_to_working()

        self.assertEqual(agent.state, "working")

    async def test_interrupt_from_working_is_idempotent(self):
        agent = _create_agent()
        agent.state = "working"

        agent.interrupt_to_working()

        self.assertEqual(agent.state, "working")


class TestAgentStateType(unittest.TestCase):
    def test_sleeping_is_valid_state(self):
        from linhai.type_hints import AgentState

        import typing

        args = typing.get_args(AgentState)
        self.assertIn("sleeping", args)
        self.assertIn("waiting_user", args)
        self.assertIn("working", args)


if __name__ == "__main__":
    unittest.main()
