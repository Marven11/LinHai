import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.callback_slot import (
    BroadcastSlot,
    ChainSlot,
    ShortCircuitSlot,
    InterruptSlot,
    AfterToolcallSlot,
)
from linhai.agent import Lifecycle


def _make_lifecycle():
    from linhai.registry import Registry
    import argparse

    registry = Registry()
    mock_agent = MagicMock()
    mock_agent.state = "waiting_user"
    mock_agent.current_disable_waiting_user_warning = False
    mock_agent.message_processor = MagicMock()
    mock_agent.message_processor.get_messages.return_value = []
    mock_agent.get_current_model = MagicMock()
    mock_agent.get_threshold_info = MagicMock(return_value=(80000, 40000, 40000, 0.5))
    mock_issue_manager = MagicMock()
    mock_issue_manager.has_unanswered_issues.return_value = False
    mock_machine_control = MagicMock()
    mock_machine_control.target_machine = "master_host"

    def get_member(member_type, member_class=None):
        if member_type == "agent":
            return mock_agent
        if member_type == "issue_manager":
            return mock_issue_manager
        if member_type == "machine_control":
            return mock_machine_control
        if member_type == "cli_args":
            return argparse.Namespace(afk=False)
        return None

    registry.get_member_typechecked = MagicMock(side_effect=get_member)
    return Lifecycle(registry)


class TestCallbackSlotTypes(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_calls_all_callbacks(self):
        lifecycle = _make_lifecycle()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        lifecycle.before_message_generation.register(cb1)
        lifecycle.before_message_generation.register(cb2)
        await lifecycle.before_message_generation.trigger()
        cb1.assert_called_once_with()
        cb2.assert_called_once_with()

    async def test_chain_passes_value_through(self):
        lifecycle = _make_lifecycle()
        msg = MagicMock(name="original")
        result = await lifecycle.before_add_new_message.trigger(msg)
        assert result is msg

    async def test_chain_replaces_value(self):
        lifecycle = _make_lifecycle()
        original = MagicMock(name="original")
        replacement = MagicMock(name="replacement")

        async def replace(msg):
            return replacement

        lifecycle.before_add_new_message.register(replace)
        result = await lifecycle.before_add_new_message.trigger(original)
        assert result is replacement

    async def test_chain_multiple_handlers_chain(self):
        lifecycle = _make_lifecycle()
        msg = MagicMock()
        calls = []

        async def handler1(m):
            calls.append("h1")
            return m

        async def handler2(m):
            calls.append("h2")
            return m

        lifecycle.before_add_new_message.register(handler1)
        lifecycle.before_add_new_message.register(handler2)
        result = await lifecycle.before_add_new_message.trigger(msg)
        assert result is msg
        assert calls == ["h1", "h2"]

    async def test_interrupt_returns_false_by_default(self):
        lifecycle = _make_lifecycle()
        result = await lifecycle.after_token_generation.trigger(
            MagicMock(), MagicMock()
        )
        assert result is False

    async def test_interrupt_returns_true_when_set(self):
        lifecycle = _make_lifecycle()

        async def interrupt(answer, segment):
            return True

        lifecycle.after_token_generation.register(interrupt)
        result = await lifecycle.after_token_generation.trigger(
            MagicMock(), MagicMock()
        )
        assert result is True

    async def test_after_toolcall_receives_arguments(self):
        lifecycle = _make_lifecycle()
        cb = AsyncMock(return_value=None)
        lifecycle.after_toolcall.register(cb)
        await lifecycle.after_toolcall.trigger(
            tool_name="test_tool",
            tool_index=3,
            status="success",
            message="done",
            toolcall_arguments={"key": "value"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        cb.assert_called_once_with(
            tool_name="test_tool",
            tool_index=3,
            status="success",
            message="done",
            toolcall_arguments={"key": "value"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

    async def test_short_circuit_returns_none_by_default(self):
        lifecycle = _make_lifecycle()
        result = await lifecycle.after_parsed_user_message.trigger(MagicMock())
        assert result is None

    async def test_short_circuit_returns_value(self):
        lifecycle = _make_lifecycle()
        replacement = MagicMock(name="replacement")

        async def replace(msg):
            return replacement

        lifecycle.after_parsed_user_message.register(replace)
        result = await lifecycle.after_parsed_user_message.trigger(MagicMock())
        assert result is replacement


if __name__ == "__main__":
    unittest.main()
