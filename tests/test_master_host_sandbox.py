import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.registry import Registry
from linhai.sandbox import BubbleWrapSandbox, NoSandbox


class TestProcessCreateSandbox(unittest.IsolatedAsyncioTestCase):
    async def test_process_create_wraps_argv_with_sandbox(self):
        sandbox = BubbleWrapSandbox(["bwrap", "--ro-bind", "/", "/"])
        registry = Registry()
        registry.register_member("process_sandbox", sandbox)
        host = MasterHostControl(registry)

        mock_process = AsyncMock()
        mock_process.pid = 999
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"out")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ) as mock_exec,
            patch("time.perf_counter", side_effect=[0.0, 1.5]),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await host.create_process(["echo", "test"], 1.0)

        called_argv = list(mock_exec.call_args[0])
        self.assertEqual(
            called_argv,
            ["bwrap", "--ro-bind", "/", "/", "echo", "test"],
        )

    async def test_process_create_no_sandbox_passes_through(self):
        registry = Registry()
        registry.register_member("process_sandbox", NoSandbox())
        host = MasterHostControl(registry)

        mock_process = AsyncMock()
        mock_process.pid = 998
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.read = AsyncMock(return_value=b"out")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ) as mock_exec,
            patch("time.perf_counter", side_effect=[0.0, 1.5]),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await host.create_process(["echo", "test"], 1.0)

        called_argv = list(mock_exec.call_args[0])
        self.assertEqual(called_argv, ["echo", "test"])


class TestTerminalCreateSandbox(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_create_wraps_bash_argv(self):
        from linhai.machine_control.master_host import terminal as terminal_mod

        sandbox = BubbleWrapSandbox(["bwrap", "--ro-bind", "/", "/"])
        registry = Registry()
        registry.register_member("process_sandbox", sandbox)
        host = MasterHostControl(registry, tmux_terminal=False)

        with patch.object(terminal_mod, "PyteTerminal") as mock_cls:
            mock_term = Mock()
            mock_term.start_reading = AsyncMock()
            mock_cls.return_value = mock_term

            result = await host.terminal_create(80, 24)

        from linhai.tool.base import ToolResultSuccess

        self.assertIsInstance(result, ToolResultSuccess)
        mock_cls.assert_called_once_with(
            columns=80,
            lines=24,
            bash_argv=["bwrap", "--ro-bind", "/", "/", "/usr/bin/env", "bash"],
        )


class TestPyteTerminalBashArgv(unittest.TestCase):
    def test_custom_bash_argv(self):
        from linhai.machine_control.master_host.terminal import PyteTerminal

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock()
            PyteTerminal(bash_argv=["custom", "bash"])

        called_argv = mock_popen.call_args[0][0]
        self.assertEqual(called_argv, ["custom", "bash"])

    def test_default_bash_argv(self):
        from linhai.machine_control.master_host.terminal import PyteTerminal

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock()
            PyteTerminal()

        called_argv = mock_popen.call_args[0][0]
        self.assertEqual(called_argv, ["/usr/bin/env", "bash"])


if __name__ == "__main__":
    unittest.main()
