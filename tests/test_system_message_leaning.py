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

        def get_member_typechecked(name, _t):
            return self.mock_registry.members[name]

        self.mock_registry.get_member_typechecked.side_effect = get_member_typechecked

        self.system_message = SystemMessage(self.mock_registry)
        self.mock_registry.members["system_message"] = self.system_message

        self.machine_control = MachineControl(self.mock_registry)
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
            "posix_shell": MagicMock(),
        }
        asyncio.run(self.call_before_helper())
        prompt = self.system_message.get_content()
        self.assertIn("INTRODUCTION - MACHINE CONTROL\n", prompt)

    def test_idempotent_when_multiple_machines(self):
        self.machine_control.machines = {
            "master_host": MagicMock(),
            "posix_shell": MagicMock(),
        }
        asyncio.run(self.call_before_helper())
        first_prompt = self.system_message.get_content()
        asyncio.run(self.call_before_helper())
        second_prompt = self.system_message.get_content()
        self.assertEqual(first_prompt, second_prompt)


class TestCustomToolcallFormatPlugin(unittest.TestCase):
    def setUp(self):
        self.mock_registry = MagicMock()
        self.mock_registry.members = {}

        def get_member_typechecked(name, _t):
            return self.mock_registry.members[name]

        self.mock_registry.get_member_typechecked.side_effect = get_member_typechecked

        self.system_message = SystemMessage(self.mock_registry)
        self.mock_registry.members["system_message"] = self.system_message

        from linhai.plugin.system_message_leaning import CustomToolcallFormatPlugin

        self.plugin = CustomToolcallFormatPlugin(self.mock_registry)

    async def call_after_helper(self, custom_format):
        mock_llm = MagicMock()
        mock_llm.get_custom_toolcall_format.return_value = custom_format
        await self.plugin.after_selecting_llm(mock_llm)

    def test_removes_examples_when_custom_format_false(self):
        asyncio.run(self.call_after_helper(False))
        prompt = self.system_message.get_content()
        self.assertNotIn("json toolcall", prompt)
        example_titles = [t for t, _ in self.system_message.examples_items]
        self.assertNotIn("TOOL CALL", example_titles)
        self.assertNotIn("SECRET", example_titles)
        self.assertNotIn("MULTIHOP MACHINES", example_titles)

    def test_keeps_examples_when_custom_format_true(self):
        asyncio.run(self.call_after_helper(True))
        example_titles = [t for t, _ in self.system_message.examples_items]
        self.assertIn("TOOL CALL", example_titles)
        self.assertIn("SECRET", example_titles)
        self.assertIn("MULTIHOP MACHINES", example_titles)

    def test_removes_introductions_when_custom_format_false(self):
        asyncio.run(self.call_after_helper(False))
        intro_titles = [t for t, _ in self.system_message.introduction_items]
        self.assertNotIn("TOOL USE", intro_titles)
        self.assertNotIn("WAITING USER AND AUTO RUN", intro_titles)

    def test_idempotent_when_false(self):
        asyncio.run(self.call_after_helper(False))
        first_prompt = self.system_message.get_content()
        asyncio.run(self.call_after_helper(False))
        second_prompt = self.system_message.get_content()
        self.assertEqual(first_prompt, second_prompt)

    def test_idempotent_when_true(self):
        asyncio.run(self.call_after_helper(True))
        first_prompt = self.system_message.get_content()
        asyncio.run(self.call_after_helper(True))
        second_prompt = self.system_message.get_content()
        self.assertEqual(first_prompt, second_prompt)

    def test_toggle_back_and_forth(self):
        asyncio.run(self.call_after_helper(False))
        example_titles_off = [t for t, _ in self.system_message.examples_items]
        self.assertNotIn("TOOL CALL", example_titles_off)

        asyncio.run(self.call_after_helper(True))
        example_titles_on = [t for t, _ in self.system_message.examples_items]
        self.assertIn("TOOL CALL", example_titles_on)
        self.assertIn("SECRET", example_titles_on)
        self.assertIn("MULTIHOP MACHINES", example_titles_on)


if __name__ == "__main__":
    unittest.main()
