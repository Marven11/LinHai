import asyncio
import unittest

from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.config import RemoteMachineConfig
from linhai.machine_control.main import MachineControl
from linhai.sandbox import NoSandbox


class TestRemoteConfigE2E(unittest.IsolatedAsyncioTestCase):
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

    async def test_disconnect_remote_machine(self):
        from linhai.tool.base import ToolResultSuccess

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

        connect_result = await mc.connect_remote_config("local-bash")
        self.assertIn("成功", connect_result.content)
        self.assertIn("local-bash", mc.machines)

        disconnect_result = await mc.disconnect_machine("local-bash")
        self.assertIsInstance(disconnect_result, ToolResultSuccess)
        self.assertNotIn("local-bash", mc.machines)
        self.assertNotIn("local-bash", mc.machine_descriptions)

    async def test_disconnect_current_machine_switches_to_master(self):
        from linhai.tool.base import ToolResultSuccess

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

        await mc.connect_remote_config("local-bash")
        mc.target_machine = "local-bash"

        disconnect_result = await mc.disconnect_machine("local-bash")
        self.assertIsInstance(disconnect_result, ToolResultSuccess)
        self.assertEqual(mc.target_machine, "master_host")
        self.assertNotIn("local-bash", mc.machines)


if __name__ == "__main__":
    unittest.main()
