import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.machine_control.main import MachineControl
from linhai.machine_control.plugin import MachineHeartbeatPlugin
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


class TestSourceChain(unittest.TestCase):
    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.register_member = Mock()
        self.mc = MachineControl(self.registry, remote_machines=[], tmux_terminal=False)

    def test_master_host_has_no_source(self):
        self.assertIsNone(self.mc.source_machines["master_host"])
        self.assertEqual(self.mc.get_source_chain("master_host"), [])

    def test_single_hop_chain(self):
        self.mc.source_machines["ssh_hop1"] = "master_host"
        self.assertEqual(self.mc.get_source_chain("ssh_hop1"), ["master_host"])

    def test_multi_hop_chain(self):
        self.mc.source_machines["ssh_hop1"] = "master_host"
        self.mc.source_machines["ssh_bash_hop2"] = "ssh_hop1"
        chain = self.mc.get_source_chain("ssh_bash_hop2")
        self.assertEqual(chain, ["ssh_hop1", "master_host"])

    def test_chain_with_cycle_stops(self):
        self.mc.source_machines["a"] = "b"
        self.mc.source_machines["b"] = "a"
        chain = self.mc.get_source_chain("a")
        self.assertIn("b", chain)

    def test_unknown_machine_returns_empty(self):
        self.assertEqual(self.mc.get_source_chain("unknown"), [])


class TestMachineHeartbeatPlugin(unittest.TestCase):
    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.register_member = Mock()
        self.mc = MachineControl(self.registry, remote_machines=[], tmux_terminal=False)
        self.plugin = MachineHeartbeatPlugin(self.registry, self.mc)

    def test_current_machine_interval(self):
        self.assertEqual(self.plugin.CURRENT_MACHINE_INTERVAL, 5.0)

    def test_other_machine_interval(self):
        self.assertEqual(self.plugin.OTHER_MACHINE_INTERVAL, 30.0)

    def test_heartbeat_skips_master_host(self):
        self.plugin._next_heartbeat = {}
        now = time.monotonic()
        new_machines = {
            mid: now
            for mid in self.mc.machines
            if mid != "master_host" and mid not in self.plugin._next_heartbeat
        }
        self.plugin._next_heartbeat.update(new_machines)
        self.assertEqual(self.plugin._next_heartbeat, {})

    def test_discover_new_machines(self):
        mock_host = AsyncMock()
        self.mc.machines["ssh_hop1"] = mock_host
        self.mc.source_machines["ssh_hop1"] = "master_host"

        now = time.monotonic()
        new_machines = {
            mid: now
            for mid in self.mc.machines
            if mid != "master_host" and mid not in self.plugin._next_heartbeat
        }
        self.plugin._next_heartbeat.update(new_machines)
        self.assertIn("ssh_hop1", self.plugin._next_heartbeat)
        self.assertEqual(self.plugin._next_heartbeat["ssh_hop1"], now)

    def test_discover_skips_already_known(self):
        mock_host = AsyncMock()
        self.mc.machines["ssh_hop1"] = mock_host
        self.mc.source_machines["ssh_hop1"] = "master_host"

        now = time.monotonic()
        self.plugin._next_heartbeat["ssh_hop1"] = now + 100
        new_machines = {
            mid: now
            for mid in self.mc.machines
            if mid != "master_host" and mid not in self.plugin._next_heartbeat
        }
        self.plugin._next_heartbeat.update(new_machines)
        self.assertEqual(self.plugin._next_heartbeat["ssh_hop1"], now + 100)

    def test_pick_earliest_due(self):
        now = time.monotonic()
        self.plugin._next_heartbeat = {
            "a": now + 10,
            "b": now - 1,
            "c": now - 5,
        }
        result = self.plugin._pick_earliest_due(now)
        self.assertEqual(result, "c")

    def test_pick_earliest_due_none_ready(self):
        now = time.monotonic()
        self.plugin._next_heartbeat = {
            "a": now + 10,
            "b": now + 5,
        }
        result = self.plugin._pick_earliest_due(now)
        self.assertIsNone(result)

    def test_pick_earliest_due_empty(self):
        result = self.plugin._pick_earliest_due(time.monotonic())
        self.assertIsNone(result)

    def test_heartbeat_updates_source_chain_on_success(self):
        async def test():
            mock_host = AsyncMock()
            mock_host.ping = AsyncMock(
                return_value=SuccessfulToolResult(content="pong")
            )
            self.mc.machines["ssh_bash_hop2"] = mock_host
            self.mc.source_machines["ssh_hop1"] = "master_host"
            self.mc.source_machines["ssh_bash_hop2"] = "ssh_hop1"
            self.mc.target_machine = "ssh_bash_hop2"

            self.plugin._next_heartbeat["ssh_bash_hop2"] = 0
            self.plugin._next_heartbeat["ssh_hop1"] = 0

            earliest_id = self.plugin._pick_earliest_due(time.monotonic())
            self.assertEqual(earliest_id, "ssh_bash_hop2")

            result = await mock_host.ping()
            self.assertNotIsInstance(result, FailedToolResult)

            interval = self.plugin._get_interval("ssh_bash_hop2")
            next_time = time.monotonic() + interval
            self.plugin._next_heartbeat["ssh_bash_hop2"] = next_time
            for source_id in self.mc.get_source_chain("ssh_bash_hop2"):
                if (
                    source_id != "master_host"
                    and source_id in self.plugin._next_heartbeat
                ):
                    source_next = time.monotonic() + self.plugin._get_interval(
                        source_id
                    )
                    self.plugin._next_heartbeat[source_id] = max(
                        self.plugin._next_heartbeat[source_id], source_next
                    )

            self.assertIn("ssh_bash_hop2", self.plugin._next_heartbeat)
            self.assertIn("ssh_hop1", self.plugin._next_heartbeat)
            self.assertNotIn("master_host", self.plugin._next_heartbeat)

            self.assertGreater(
                self.plugin._next_heartbeat["ssh_bash_hop2"], time.monotonic()
            )
            self.assertGreater(
                self.plugin._next_heartbeat["ssh_hop1"], time.monotonic()
            )

        asyncio.run(test())

    def test_heartbeat_no_update_on_failure(self):
        async def test():
            mock_host = AsyncMock()
            mock_host.ping = AsyncMock(
                return_value=FailedToolResult(content="connection lost")
            )
            self.mc.machines["ssh_hop1"] = mock_host
            self.mc.source_machines["ssh_hop1"] = "master_host"
            self.mc.target_machine = "ssh_hop1"

            self.plugin._next_heartbeat["ssh_hop1"] = 0

            earliest_id = self.plugin._pick_earliest_due(time.monotonic())
            self.assertEqual(earliest_id, "ssh_hop1")

            result = await mock_host.ping()
            self.assertIsInstance(result, FailedToolResult)

            interval = self.plugin._get_interval("ssh_hop1")
            next_time = time.monotonic() + interval
            self.plugin._next_heartbeat["ssh_hop1"] = next_time

            self.assertGreater(
                self.plugin._next_heartbeat["ssh_hop1"], time.monotonic()
            )

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
