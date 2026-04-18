import unittest
import asyncio
from unittest.mock import MagicMock

from linhai.base import SystemMessage
from linhai.machine_control.main import MachineControl
from linhai.plugin.system_message_leaning import MachineControlIntroductionPlugin


class TestMachineControlPlugin(unittest.TestCase):
    def setUp(self):
        self.mock_registry = MagicMock()
        self.mock_registry.members = {}

        def get_member_typechecked(name, t):
            return self.mock_registry.members[name]

        self.mock_registry.get_member_typechecked.side_effect = get_member_typechecked

        self.system_message = SystemMessage(self.mock_registry)
        self.mock_registry.members["system_message"] = self.system_message

        self.machine_control = MachineControl(self.mock_registry, remote_machines=[])
        self.mock_registry.members["machine_control"] = self.machine_control

        self.plugin = MachineControlIntroductionPlugin(self.mock_registry)

    async def call_before_helper(self):
        await self.plugin.before_message_generation()

    def test_removes_machine_control_when_only_master_host(self):
        self.machine_control.machines = {"master_host": MagicMock()}
        asyncio.run(self.call_before_helper())
        prompt = self.system_message.get_content()
        self.assertNotIn("INTRODUCTION - MACHINE CONTROL\n", prompt)

    def test_adds_machine_control_when_multiple_machines(self):
        self.machine_control.machines = {
            "master_host": MagicMock(),
            "ssh_host": MagicMock(),
        }
        asyncio.run(self.call_before_helper())
        prompt = self.system_message.get_content()
        self.assertIn("INTRODUCTION - MACHINE CONTROL\n", prompt)

    def test_idempotent_when_multiple_machines(self):
        self.machine_control.machines = {
            "master_host": MagicMock(),
            "ssh_host": MagicMock(),
        }
        asyncio.run(self.call_before_helper())
        first_prompt = self.system_message.get_content()
        asyncio.run(self.call_before_helper())
        second_prompt = self.system_message.get_content()
        self.assertEqual(first_prompt, second_prompt)


if __name__ == "__main__":
    unittest.main()
