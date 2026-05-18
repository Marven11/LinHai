import unittest
from unittest.mock import Mock, AsyncMock, patch
from linhai.plugin.command_hints import SudoBashHintPlugin
from linhai.tool.base import SuccessfulToolResult


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
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("connect_posix_shell_as_machine", result.warnings[0].message)

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
        self.assertIsNotNone(result1)
        self.assertEqual(len(result1.warnings), 1)

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

    async def test_python_c_shows_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["python", "-c", "print(1)"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("python -c", result.warnings[0].message)
        self.assertIn("python repl", result.warnings[0].message)

    async def test_python3_c_shows_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["python3", "-c", "print(1)"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)

    async def test_venv_python_c_shows_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["venv/bin/python", "-c", "print(1)"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)

    async def test_uv_run_python_c_shows_hint(self):
        mock_agent = Mock()
        mock_agent.message_processor = Mock()
        mock_agent.message_processor.add_new_message = AsyncMock()
        self.registry.get_member_typechecked = Mock(return_value=mock_agent)

        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["uv", "run", "python", "-c", "print(1)"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.warnings), 1)

    async def test_python_no_c_no_hint(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message=None,
            toolcall_arguments={"argv": ["python", "script.py"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

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

        self.machine_control = MachineControl(self.registry)

    async def test_add_posix_shell_machine_duplicate_id(self):
        from linhai.tool.base import FailedToolResult

        result = await self.machine_control.add_posix_shell_machine(
            "master_host", "123"
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("机器ID已存在", result.content)

    async def test_add_posix_shell_machine_source_not_found(self):
        from linhai.tool.base import FailedToolResult

        result = await self.machine_control.add_posix_shell_machine(
            "new_machine", "123", source_machine="nonexistent"
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("源机器不存在", result.content)

    async def test_add_posix_shell_machine_process_not_found(self):
        from linhai.tool.base import FailedToolResult

        result = await self.machine_control.add_posix_shell_machine(
            "new_machine", "99999"
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("进程不存在", result.content)

    async def test_add_posix_shell_machine_connect_failure(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host
        self.machine_control.remote_shell_control = "python"

        with (
            patch(
                "linhai.machine_control.main._check_shell_compatibility",
                new_callable=AsyncMock,
                return_value=(True, "bash"),
            ),
            patch.object(
                PosixShellControl, "connect", new_callable=AsyncMock, return_value=False
            ),
        ):
            from linhai.tool.base import FailedToolResult

            result = await self.machine_control.add_posix_shell_machine(
                "bash_machine", "123"
            )
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("连接posix shell进程失败", result.content)

    async def test_add_posix_shell_machine_success(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.tool.base import SuccessfulToolResult

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host

        with (
            patch(
                "linhai.machine_control.main._check_shell_compatibility",
                new_callable=AsyncMock,
                return_value=(True, "bash"),
            ),
            patch.object(
                PosixShellControl, "connect", new_callable=AsyncMock, return_value=True
            ),
        ):
            result = await self.machine_control.add_posix_shell_machine(
                "bash_machine", "123"
            )
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("bash_machine", result.content)
            self.assertIn("bash_machine", self.machine_control.machines)
            self.assertIn(
                "Posix shell进程主机",
                self.machine_control.machine_descriptions["bash_machine"],
            )

    async def test_add_posix_shell_machine_source_machine_parameter(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.tool.base import FailedToolResult

        mock_remote = Mock()
        mock_remote.get_process = Mock(return_value=None)
        self.machine_control.machines["remote_host"] = mock_remote

        result = await self.machine_control.add_posix_shell_machine(
            "bash_machine", "456", source_machine="remote_host"
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("进程不存在", result.content)
        mock_remote.get_process.assert_called_once_with("456")


class TestConnectBashAsMachineTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.registry.send_if_exists = AsyncMock()
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.registry)

    def test_tool_registered(self):
        from linhai.machine_control.tools import register_machine_control_tools

        toolset = register_machine_control_tools(self.machine_control)
        tool_names = list(toolset.tools.keys())
        self.assertIn("connect_posix_shell_as_machine", tool_names)


class TestPosixShellControlHostOptional(unittest.IsolatedAsyncioTestCase):
    def test_ssh_machine_control_without_host(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )

        ctrl = PosixShellControl(registry=Mock())
        self.assertIsNotNone(ctrl)
        self.assertIsNone(ctrl.transport)

    def test_ssh_machine_control_with_host(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )

        ctrl = PosixShellControl(registry=Mock(), host="example.com", port=2222)
        self.assertIsNotNone(ctrl)


class TestCheckShellCompatibility(unittest.IsolatedAsyncioTestCase):
    def _make_process_mock(self, stdout: bytes, write_success: bool = True) -> Mock:
        from linhai.machine_control.process import ProcessWriteResult, ProcessReadResult

        mock_process = Mock()
        mock_process.stdio_write = AsyncMock(
            return_value=ProcessWriteResult(
                pid="1", success=write_success, message="ok"
            )
        )
        mock_process.stdio_read = AsyncMock(
            return_value=ProcessReadResult(
                pid="1",
                success=True,
                stdout=stdout,
                stderr=b"",
                exit_note="",
            )
        )
        return mock_process

    async def test_bash_is_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(
            b'echo "LH0=$0"; echo "LHS=$SHELL"\nLH0=bash\nLHS=/bin/bash\nuser@host:~$ '
        )
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "bash")

    async def test_zsh_is_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(
            b'echo "LH0=$0"; echo "LHS=$SHELL"\nLH0=zsh\nLHS=/usr/bin/zsh\n'
        )
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "zsh")

    async def test_fish_is_not_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=\nLHS=/usr/bin/fish\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "fish")

    async def test_nushell_is_not_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=\nLHS=/home/user/.local/bin/nu\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "nu")

    async def test_xonsh_is_not_compatible_via_lh0(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=xonsh\nLHS=/usr/bin/xonsh\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "xonsh")

    async def test_pwsh_is_not_compatible_via_lh0(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=pwsh\nLHS=/usr/bin/pwsh\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "pwsh")

    async def test_write_failure_returns_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"", write_success=False)
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "")

    async def test_no_marker_output_returns_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"some text without markers\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "")

    async def test_tcsh_is_not_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=\nLHS=/bin/tcsh\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "tcsh")

    async def test_ansi_codes_stripped(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(
            b"\x1b[32mLH0=\x1b[0m\n\x1b[32mLHS=/usr/bin/fish\x1b[0m\n"
        )
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertFalse(compatible)
        self.assertEqual(shell_name, "fish")

    async def test_bash_from_fish_is_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=bash\nLHS=/usr/bin/fish\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "bash")

    async def test_zsh_from_fish_is_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=zsh\nLHS=/usr/bin/fish\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "zsh")

    async def test_lh0_empty_lhs_no_path_compatible(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=\nLHS=\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "")

    async def test_login_shell_prefix_stripped(self):
        from linhai.machine_control.main import _check_shell_compatibility

        mock_process = self._make_process_mock(b"LH0=-bash\nLHS=/bin/bash\n")
        compatible, shell_name = await _check_shell_compatibility(mock_process)
        self.assertTrue(compatible)
        self.assertEqual(shell_name, "bash")


class TestAddPosixShellIncompatibleShell(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = Mock()
        self.registry.send_if_exists = AsyncMock()
        from linhai.machine_control import MachineControl

        self.machine_control = MachineControl(self.registry)

    async def test_fish_shell_rejected(self):
        from linhai.tool.base import FailedToolResult

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host

        with patch(
            "linhai.machine_control.main._check_shell_compatibility",
            new_callable=AsyncMock,
            return_value=(False, "fish"),
        ):
            result = await self.machine_control.add_posix_shell_machine("remote", "123")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("fish", result.content)
            self.assertIn("posix", result.content)

    async def test_bash_shell_accepted(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.tool.base import SuccessfulToolResult

        mock_host = Mock()
        mock_process = Mock()
        mock_host.get_process = Mock(return_value=mock_process)
        self.machine_control.machines["master_host"] = mock_host

        with (
            patch(
                "linhai.machine_control.main._check_shell_compatibility",
                new_callable=AsyncMock,
                return_value=(True, "bash"),
            ),
            patch.object(
                PosixShellControl, "connect", new_callable=AsyncMock, return_value=True
            ),
        ):
            result = await self.machine_control.add_posix_shell_machine("remote", "123")
            self.assertIsInstance(result, SuccessfulToolResult)


if __name__ == "__main__":
    unittest.main()
