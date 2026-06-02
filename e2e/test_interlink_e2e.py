import asyncio
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from linhai.agent.messages import RuntimeMessage
from linhai.plugin.interlink import InterlinkPlugin
from linhai.registry import Registry

pytestmark = pytest.mark.asyncio


async def test_interlink_two_agents_communication():
    temp_dir = tempfile.mkdtemp()
    interlink_dir = Path(temp_dir) / "interlink" / "test_channel"
    interlink_file = interlink_dir / "INTERLINK.txt"

    registry_a = Registry()
    plugin_a = InterlinkPlugin(registry_a, "test_channel")
    plugin_a.interlink_dir = interlink_dir
    plugin_a.interlink_file = interlink_file

    mock_agent_a = Mock()
    mock_agent_a.message_processor = Mock()
    mock_agent_a.message_processor.add_new_message = AsyncMock()

    mock_system_message = Mock()
    mock_ts = Mock()

    def get_member_a(name, t=None):
        if name == "system_message":
            return mock_system_message
        if name == "task_supervisor":
            return mock_ts
        if name == "agent":
            return mock_agent_a
        return None

    registry_a.get_member_typechecked = get_member_a
    registry_a.send_if_exists = AsyncMock()

    await plugin_a.before_agent_loop(mock_agent_a)
    assert interlink_file.exists()

    test_uuid = str(uuid.uuid4())
    interlink_file.write_text(f"{plugin_a.agent_id} {test_uuid}\n", encoding="utf-8")

    await plugin_a.before_message_generation()

    add_calls = mock_agent_a.message_processor.add_new_message.call_args_list
    assert len(add_calls) >= 2
    diff_msg = add_calls[-1][0][0]
    assert isinstance(diff_msg, RuntimeMessage)
    assert test_uuid in diff_msg.get_content()


async def test_interlink_agent_receives_only_new_content():
    temp_dir = tempfile.mkdtemp()
    interlink_dir = Path(temp_dir) / "interlink" / "test_channel"
    interlink_file = interlink_dir / "INTERLINK.txt"

    registry = Registry()
    plugin = InterlinkPlugin(registry, "test_channel")
    plugin.interlink_dir = interlink_dir
    plugin.interlink_file = interlink_file

    mock_agent = Mock()
    mock_agent.message_processor = Mock()
    mock_agent.message_processor.add_new_message = AsyncMock()

    mock_system_message = Mock()
    mock_ts = Mock()

    def get_member(name, t=None):
        if name == "system_message":
            return mock_system_message
        if name == "task_supervisor":
            return mock_ts
        if name == "agent":
            return mock_agent
        return None

    registry.get_member_typechecked = get_member
    registry.send_if_exists = AsyncMock()

    await plugin.before_agent_loop(mock_agent)

    first_uuid = str(uuid.uuid4())
    interlink_file.write_text(f"@aaaa {first_uuid}\n", encoding="utf-8")
    await plugin.before_message_generation()

    second_uuid = str(uuid.uuid4())
    interlink_file.write_text(
        f"@aaaa {first_uuid}\n@bbbb {second_uuid}\n", encoding="utf-8"
    )
    await plugin.before_message_generation()

    add_calls = mock_agent.message_processor.add_new_message.call_args_list
    last_msg = add_calls[-1][0][0]
    assert isinstance(last_msg, RuntimeMessage)
    content = last_msg.get_content()
    assert second_uuid in content


async def test_interlink_monitor_wakes_waiting_agent():
    temp_dir = tempfile.mkdtemp()
    interlink_file = Path(temp_dir) / "INTERLINK.txt"
    interlink_file.write_text("", encoding="utf-8")

    from linhai.agent.state_machine import AgentStateMachine

    registry = Registry()
    state_machine = AgentStateMachine(registry)
    state_machine.state = "waiting_user"

    plugin = InterlinkPlugin(registry, "test_channel")
    plugin.interlink_file = interlink_file
    plugin._old_content = ""

    mock_agent = Mock()
    call_count = 0

    async def fake_sleep(duration):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            test_uuid = str(uuid.uuid4())
            interlink_file.write_text(f"@cccc {test_uuid}\n", encoding="utf-8")
        if call_count >= 2:
            raise asyncio.CancelledError()

    async def run_test():
        import unittest.mock as um

        with um.patch("linhai.plugin.interlink.asyncio.sleep", side_effect=fake_sleep):
            await plugin._monitor_loop(mock_agent)

    with pytest.raises(asyncio.CancelledError):
        await run_test()

    assert state_machine.state == "working"
    assert plugin._old_content == ""
