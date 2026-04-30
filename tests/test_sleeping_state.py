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
        llm_fallback_duration_map={"test-llm": 120},
    )

    agent = Agent(
        llm_manager=llm_manager,
        compress_threshold=800,
        registry=registry,
        pinned_messages=[],
    )
    agent.registry = registry

    umh_mock = MagicMock()
    umh_mock.has_message = MagicMock(return_value=False)
    umh_mock.receive_and_dispatch = AsyncMock(return_value=False)

    def _get_member(name, t):
        if name == "user_message_handler":
            return umh_mock
        return agent

    registry.get_member_typechecked = MagicMock(side_effect=_get_member)
    agent.user_message_handler = umh_mock
    return agent


class TestSleepTool(unittest.IsolatedAsyncioTestCase):
    async def test_sleep_tool_waits_and_returns_working(self):
        agent = _create_agent()
        toolset = agent.state_machine.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        self.assertEqual(agent.state_machine.state, "waiting_user")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

        result = await sleep_fn(seconds=0.1)

        self.assertEqual(agent.state_machine.state, "working")
        self.assertIsNone(agent.state_machine.sleeping_since)
        self.assertIsNone(agent.state_machine.sleeping_deadline)

        from linhai.tool.base import SuccessfulToolResult

        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertIn("睡眠完成", result.content)


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


class TestSleepToolTiming(unittest.IsolatedAsyncioTestCase):
    async def test_second_tool_runs_after_sleep(self):
        agent = _create_agent()
        toolset = agent.state_machine.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        execution_order: list[str] = []

        async def fake_other_tool():
            execution_order.append("other_tool")

        async def call_tools_concurrently():
            await sleep_fn(seconds=0.1)
            execution_order.append("sleep_done")

        task = asyncio.create_task(call_tools_concurrently())
        await asyncio.sleep(0.01)
        self.assertEqual(execution_order, [])
        await task
        await fake_other_tool()

        self.assertEqual(execution_order, ["sleep_done", "other_tool"])

    async def test_sleep_then_another_tool_sequential(self):
        agent = _create_agent()
        toolset = agent.state_machine.generate_sleep_toolset()
        sleep_fn = toolset.get_tool("sleep")

        execution_order: list[str] = []

        await sleep_fn(seconds=0.1)
        execution_order.append("after_sleep")
        execution_order.append("other_tool")

        self.assertEqual(execution_order, ["after_sleep", "other_tool"])
        self.assertEqual(agent.state_machine.state, "working")


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
