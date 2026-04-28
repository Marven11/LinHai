import asyncio
import fcntl
import os
import pty as pty_module
import unittest

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.machine_control.master_host.process import LocalPtyProcess
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import ToolResultSuccess


class TestPtyConnectE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_pty_bash(
        self,
    ) -> tuple[LocalPtyProcess, asyncio.subprocess.Process]:
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        master_fd, slave_fd = pty_module.openpty()
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/env",
            "bash",
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
        )
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)

        async def _on_exit(pid: str) -> None:
            pass

        lp = LocalPtyProcess(process, master_fd, slave_fd, on_exit=_on_exit)
        return lp, process

    async def _cleanup(self, control, pty_proc, subprocess):
        await control.disconnect()
        pty_proc._close_fds()
        if subprocess.returncode is None:
            subprocess.terminate()
            await asyncio.wait_for(subprocess.wait(), timeout=5.0)

    async def test_connect_pty_bash_and_use_tools(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())

        pty_proc, subprocess = await self._create_pty_bash()
        await asyncio.sleep(1.0)

        control = PosixShellControl(registry=registry)
        connected = await control.connect(pty_proc)
        self.assertTrue(connected, "连接pty bash失败")

        try:
            ping_result = await control.ping()
            self.assertIsInstance(
                ping_result, ToolResultSuccess, f"ping失败: {ping_result}"
            )

            result = await control.call_tool("read_file", {"filepath": "/etc/hostname"})
            self.assertIsInstance(result, ToolResultSuccess)

            result2 = await control.call_tool("get_absolute_path", {"path": "/tmp"})
            self.assertIsInstance(result2, ToolResultSuccess)
        finally:
            await self._cleanup(control, pty_proc, subprocess)

    async def test_pty_connect_wait_60s_then_concurrent_tools(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())

        pty_proc, subprocess = await self._create_pty_bash()
        await asyncio.sleep(1.0)

        control = PosixShellControl(registry=registry)
        connected = await control.connect(pty_proc)
        self.assertTrue(connected, "连接pty bash失败")

        try:
            await asyncio.sleep(60)

            results = await asyncio.gather(
                control.ping(),
                control.call_tool("read_file", {"filepath": "/etc/hostname"}),
                control.call_tool("get_absolute_path", {"path": "/tmp"}),
                return_exceptions=True,
            )

            self.assertEqual(len(results), 3)
            for i, r in enumerate(results):
                self.assertFalse(
                    isinstance(r, Exception),
                    f"工具调用{i}抛出异常: {r}",
                )
                self.assertIsInstance(r, ToolResultSuccess, f"工具调用{i}失败: {r}")
        finally:
            await self._cleanup(control, pty_proc, subprocess)


if __name__ == "__main__":
    unittest.main()
