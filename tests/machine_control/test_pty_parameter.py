import unittest
import inspect
from unittest.mock import Mock

from linhai.machine_control.tools import register_machine_control_tools


class TestPtyParameter(unittest.TestCase):
    def test_process_create_no_pty_parameter(self):
        mock_machine_control = Mock()
        mock_machine_control.machines = {"master_host": Mock()}
        mock_machine_control.target_machine = "master_host"

        toolset = register_machine_control_tools(mock_machine_control)
        tool_func = toolset.get_tool("process_create")

        signature = inspect.signature(tool_func)
        self.assertNotIn("pty", signature.parameters)


if __name__ == "__main__":
    unittest.main()
