import asyncio
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from linhai.machine_control.main import MachineControl
from linhai.machine_control.plugin import MachineHeartbeatPlugin
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class TestSourceChain(unittest.TestCase):
    def setUp(self):
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.register_member = Mock()
        self.mc = MachineControl(self.registry, tmux_terminal=False)

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
        self.mc = MachineControl(self.registry, tmux_terminal=False)
        self.plugin = MachineHeartbeatPlugin(self.registry, self.mc)

    def test_current_machine_interval(self):
        self.assertEqual(self.plugin.CURRENT_MACHINE_INTERVAL, 5.0)

    def test_other_machine_interval(self):
        self.assertEqual(self.plugin.OTHER_MACHINE_INTERVAL, 30.0)

    def test_heartbeat_skips_master_host(self):
        async def test():
            self.mc.target_machine = "master_host"
            self.plugin._last_heartbeat = {}
            self.plugin._inflight = set()
            await asyncio.sleep(0.1)
            self.assertEqual(self.plugin._last_heartbeat, {})

        asyncio.run(test())

    def test_heartbeat_updates_source_chain_on_success(self):
        async def test():
            mock_host = AsyncMock()
            mock_host.call_tool = AsyncMock(
                return_value=ToolResultSuccess(content="pong")
            )
            self.mc.machines["ssh_bash_hop2"] = mock_host
            self.mc.source_machines["ssh_hop1"] = "master_host"
            self.mc.source_machines["ssh_bash_hop2"] = "ssh_hop1"
            self.mc.target_machine = "ssh_bash_hop2"

            with patch(
                "linhai.machine_control.plugin.SshMachineControl",
                type(mock_host),
            ):
                result = await mock_host.call_tool("ping", {})
                self.assertNotIsInstance(result, ToolResultFailed)

                self.plugin._last_heartbeat["ssh_bash_hop2"] = time.monotonic()
                for source_id in self.mc.get_source_chain("ssh_bash_hop2"):
                    if source_id != "master_host":
                        self.plugin._last_heartbeat[source_id] = (
                            self.plugin._last_heartbeat["ssh_bash_hop2"]
                        )

                self.assertIn("ssh_bash_hop2", self.plugin._last_heartbeat)
                self.assertIn("ssh_hop1", self.plugin._last_heartbeat)
                self.assertNotIn("master_host", self.plugin._last_heartbeat)

        asyncio.run(test())

    def test_heartbeat_no_update_on_failure(self):
        async def test():
            mock_host = AsyncMock()
            mock_host.call_tool = AsyncMock(
                return_value=ToolResultFailed(content="connection lost")
            )
            self.mc.machines["ssh_hop1"] = mock_host
            self.mc.source_machines["ssh_hop1"] = "master_host"
            self.mc.target_machine = "ssh_hop1"

            result = await mock_host.call_tool("ping", {})
            self.assertIsInstance(result, ToolResultFailed)
            self.assertEqual(self.plugin._last_heartbeat, {})

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
