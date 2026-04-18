import asyncio
import json
import unittest
from pathlib import Path

from linhai.machine_control.trojan.ssh_transport import SshTrojanTransport
from tests.test_helpers import _AsyncioProcessAdapter
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.config import RemoteMachineConfig
from linhai.machine_control.main import MachineControl
from linhai.sandbox import NoSandbox


class TestRemoteConfigE2E(unittest.IsolatedAsyncioTestCase):
    async def test_list_remote_configs_empty(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        registry.register_member("process_sandbox", NoSandbox())
        mc = MachineControl(registry, remote_machines=[])
        result = await mc.list_remote_configs()
        self.assertIn("没有预设", result.content)

    async def test_list_remote_configs_with_entries(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        registry.register_member("process_sandbox", NoSandbox())
        configs = [
            RemoteMachineConfig(
                name="test-server",
                argv=["ssh", "user@host"],
                description="Test server",
            ),
        ]
        mc = MachineControl(registry, remote_machines=configs)
        result = await mc.list_remote_configs()
        self.assertIn("test-server", result.content)
        self.assertIn("Test server", result.content)

    async def test_connect_remote_config_not_found(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        registry.register_member("process_sandbox", NoSandbox())
        mc = MachineControl(registry, remote_machines=[])
        result = await mc.connect_remote_config("nonexistent")
        self.assertIn("未找到", result.content)

    async def test_connect_remote_config_local_bash(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        registry.register_member("process_sandbox", NoSandbox())
        configs = [
            RemoteMachineConfig(
                name="local-bash",
                argv=["bash"],
                description="Local bash",
            ),
        ]
        mc = MachineControl(registry, remote_machines=configs)

        result = await mc.connect_remote_config("local-bash")
        self.assertIn("成功", result.content)
        self.assertIn("local-bash", mc.machines)

        host_control = mc.machines["local-bash"]
        ping_result = await host_control.ping()
        self.assertIsInstance(ping_result, type(result))
        self.assertNotIn(
            "失败", ping_result.content if hasattr(ping_result, "content") else ""
        )

    async def test_connect_remote_config_already_connected(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        registry.register_member("process_sandbox", NoSandbox())
        configs = [
            RemoteMachineConfig(
                name="local-bash",
                argv=["bash"],
            ),
        ]
        mc = MachineControl(registry, remote_machines=configs)

        result1 = await mc.connect_remote_config("local-bash")
        self.assertIn("成功", result1.content)

        result2 = await mc.connect_remote_config("local-bash")
        self.assertIn("已存在", result2.content)


if __name__ == "__main__":
    unittest.main()
