import unittest
from unittest.mock import Mock, AsyncMock, patch
from linhai.plugin.sudo_bash_hint import SudoBashHintPlugin
from linhai.tool.base import ToolResultSuccess


class TestSudoBashHintPlugin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.plugin = SudoBashHintPlugin(self.registry)

    async def test_after_toolcall_not_process_create(self):
        result = await self.plugin.after_toolcall(
            tool_name="other_tool",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "ls"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_not_success(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="failed",
            message=None,
            toolcall_arguments={"argv": ["sudo", "ls"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_no_argv(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_not_sudo(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["ls", "-lah"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_sudo_bash_no_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "bash"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_after_toolcall_sudo_sh_no_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "sh"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_after_toolcall_sudo_non_bash_shows_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "apt", "install", "vim"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = mock_agent.message_processor.add_new_message.call_args[0][0]
        self.assertIn("connect_bash_as_machine", call_args.message)

    async def test_after_toolcall_sudo_path_bash_no_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "/bin/bash"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_after_toolcall_sudo_flags_then_bash_no_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "-S", "bash"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)
        mock_agent.message_processor.add_new_message.assert_not_called()

    async def test_after_toolcall_time_window_suppresses_repeat(self):
        import time

        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result1 = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "ls"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result1)
        self.assertEqual(mock_agent.message_processor.add_new_message.call_count, 1)

        result2 = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=1,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["sudo", "cat", "/etc/hosts"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result2)
        self.assertEqual(mock_agent.message_processor.add_new_message.call_count, 1)

    def test_register_method(self):
        mock_lifecycle = Mock()
        mock_lifecycle.after_toolcall.register = Mock()
        self.plugin.register(mock_lifecycle)
        mock_lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
        )


class TestAddBashMachine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.registry.send_if_exists = AsyncMock()
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.registry, remote_machines=[])

    async def test_add_bash_machine_duplicate_id(self):
        from linhai.tool.base import ToolResultFailed

        result = await self.machine_control.add_bash_machine("master_host", "123")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("机器ID已存在", result.content)

    async def test_add_bash_machine_source_not_found(self):
        from linhai.tool.base import ToolResultFailed

        result = await self.machine_control.add_bash_machine(
            "new_machine", "123", source_machine="nonexistent"
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("源机器不存在", result.content)

    async def test_add_bash_machine_process_not_found(self):
        from linhai.tool.base import ToolResultFailed

        result = await self.machine_control.add_bash_machine("new_machine", "99999")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("进程不存在", result.content)

    async def test_add_bash_machine_connect_failure(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host

        with patch.object(
            SshMachineControl, "connect", new_callable=AsyncMock, return_value=False
        ):
            from linhai.tool.base import ToolResultFailed

            result = await self.machine_control.add_bash_machine("bash_machine", "123")
            self.assertIsInstance(result, ToolResultFailed)
            self.assertIn("连接bash进程失败", result.content)

    async def test_add_bash_machine_success(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
        from linhai.tool.base import ToolResultSuccess

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host

        with patch.object(
            SshMachineControl, "connect", new_callable=AsyncMock, return_value=True
        ):
            result = await self.machine_control.add_bash_machine("bash_machine", "123")
            self.assertIsInstance(result, ToolResultSuccess)
            self.assertIn("bash_machine", result.content)
            self.assertIn("bash_machine", self.machine_control.machines)
            self.assertIn(
                "Bash进程主机",
                self.machine_control.machine_descriptions["bash_machine"],
            )

    async def test_add_bash_machine_source_machine_parameter(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
        from linhai.tool.base import ToolResultFailed

        mock_remote = Mock()
        mock_remote.get_process = Mock(return_value=None)
        self.machine_control.machines["remote_host"] = mock_remote

        result = await self.machine_control.add_bash_machine(
            "bash_machine", "456", source_machine="remote_host"
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("进程不存在", result.content)
        mock_remote.get_process.assert_called_once_with("456")


class TestConnectBashAsMachineTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.registry.send_if_exists = AsyncMock()
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.registry, remote_machines=[])

    def test_tool_registered(self):
        from linhai.machine_control.tools import register_machine_control_tools

        toolset = register_machine_control_tools(self.machine_control)
        tool_names = list(toolset.tools.keys())
        self.assertIn("connect_bash_as_machine", tool_names)


class TestSshMachineControlHostOptional(unittest.IsolatedAsyncioTestCase):
    def test_ssh_machine_control_without_host(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl

        ctrl = SshMachineControl(registry=Mock())
        self.assertIsNotNone(ctrl)
        self.assertIsNone(ctrl.transport)

    def test_ssh_machine_control_with_host(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl

        ctrl = SshMachineControl(registry=Mock(), host="example.com", port=2222)
        self.assertIsNotNone(ctrl)


if __name__ == "__main__":
    unittest.main()
