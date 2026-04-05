import unittest
import asyncio
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
        toolset = agent.state_machine.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        self.assertEqual(agent.state_machine.state, "waiting_user")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

        result = await sleep_fn(seconds=5.0)

        self.assertEqual(agent.state_machine.state, "sleeping")
        self.assertIsNotNone(agent.state_machine.sleeping_since)
        self.assertIsNotNone(agent.state_machine.sleeping_deadline)

        expected_deadline = agent.state_machine.sleeping_since + timedelta(seconds=5.0)
        self.assertAlmostEqual(
            (agent.state_machine.sleeping_deadline - expected_deadline).total_seconds(),
            0.0,
            places=1,
        )

        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)


class TestStateSleeping(unittest.IsolatedAsyncioTestCase):
    async def test_state_sleeping_completes(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=0.1)
        )

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        await agent.state_sleeping()

        self.assertEqual(agent.state_machine.state, "working")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)
        agent.message_processor.add_new_message.assert_called_once()

    async def test_state_sleeping_interrupted_by_state_change(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=10)
        )

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        async def interrupt_after_delay():
            await asyncio.sleep(0.05)
            agent.state_machine.interrupt_to_working()

        task = asyncio.create_task(interrupt_after_delay())
        await agent.state_sleeping()
        await task

        self.assertEqual(agent.state_machine.state, "working")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

    async def test_run_handles_sleeping_state(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=0.1)
        )

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        call_count = 0

        async def fake_state_sleeping():
            nonlocal call_count
            call_count += 1
            agent.state_machine.finish_sleeping()
            agent.state_machine.transition_to_waiting_user()

        agent.state_sleeping = fake_state_sleeping

        agent.state_waiting_user = AsyncMock()
        agent.state_working = AsyncMock()

        async def fake_state_waiting_user():
            raise asyncio.CancelledError()

        agent.state_waiting_user = fake_state_waiting_user

        await agent.run()

        self.assertEqual(call_count, 1)


class TestInterruptToWorking(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_from_sleeping(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=100)
        )

        agent.state_machine.interrupt_to_working()

        self.assertEqual(agent.state_machine.state, "working")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

    async def test_interrupt_from_waiting_user(self):
        agent = _create_agent()
        agent.state_machine.interrupt_to_working()

        self.assertEqual(agent.state_machine.state, "working")

    async def test_interrupt_from_working_is_idempotent(self):
        agent = _create_agent()
        agent.state_machine.transition_to_working()

        agent.state_machine.interrupt_to_working()

        self.assertEqual(agent.state_machine.state, "working")


class TestSleepingUserMessageInterrupt(unittest.IsolatedAsyncioTestCase):
    async def test_user_message_interrupts_sleep(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=10)
        )

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        async def send_user_message_after_delay():
            await asyncio.sleep(0.05)
            agent.user_message_handler.has_message = MagicMock(return_value=True)
            agent.user_message_handler.receive_and_dispatch = AsyncMock(
                return_value=True
            )

        task = asyncio.create_task(send_user_message_after_delay())
        await agent.state_sleeping()
        await task

        self.assertEqual(agent.state_machine.state, "working")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

    async def test_non_interrupt_command_continues_sleep(self):
        agent = _create_agent()
        agent.state_machine.transition_to_sleeping(
            datetime.now(), datetime.now() + timedelta(seconds=0.2)
        )

        agent.message_processor = MagicMock()
        agent.message_processor.add_new_message = AsyncMock()

        has_message_calls = [True, False]

        def has_message_side_effect():
            if has_message_calls:
                return has_message_calls.pop(0)
            return False

        agent.user_message_handler.has_message = MagicMock(
            side_effect=has_message_side_effect
        )
        agent.user_message_handler.receive_and_dispatch = AsyncMock(return_value=False)

        await agent.state_sleeping()

        self.assertEqual(agent.state_machine.state, "working")
        agent.message_processor.add_new_message.assert_called_once()


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
