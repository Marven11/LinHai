import asyncio
import os
import pathlib
import unittest

from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.master_host.process import LocalPtyProcess
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import (
    SuccessfulToolResult,
    FileContentToolResult,
)

LARGE_FILE_RELATIVE = "linhai/machine_control/tools.py"


def _make_registry() -> Registry:
    registry = Registry()
    ts = PlainTaskSupervisor()
    registry.register_member("task_supervisor", ts)
    return registry


class TestBashHostE2e(unittest.IsolatedAsyncioTestCase):
    async def _create_pty_bash(self) -> LocalPtyProcess | None:
        import fcntl
        import pty as pty_module

        master_fd, slave_fd = pty_module.openpty()
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
        try:
            process = await asyncio.create_subprocess_exec(
                "/usr/bin/env",
                "bash",
                "-i",
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
            )
            await asyncio.sleep(0.5)
            if process.returncode is not None:
                os.close(master_fd)
                os.close(slave_fd)
                return None
            return LocalPtyProcess(
                process,
                master_fd,
                slave_fd,
                on_exit=self._noop_on_exit,
            )
        except OSError:
            os.close(master_fd)
            os.close(slave_fd)
            return None

    @staticmethod
    async def _noop_on_exit(pid: str) -> None:
        pass

    async def _connect_bash_host(
        self,
    ) -> tuple[BashHostControl, LocalPtyProcess] | None:
        pty_proc = await self._create_pty_bash()
        if pty_proc is None:
            return None
        registry = _make_registry()
        host = BashHostControl(registry=registry)
        connected = await host.connect(pty_proc)
        if not connected:
            if pty_proc.returncode is None:
                await pty_proc.kill()
            return None
        return host, pty_proc

    async def test_write_and_read_file(self) -> None:
        result = await self._connect_bash_host()
        if result is None:
            self.skipTest("Failed to create/connect bash host (CI environment)")
        host, pty_proc = result

        try:
            tmp_path = "/tmp/linhai_bash_e2e_write_test.txt"
            content = "hello world from bash e2e test\nline 2\nline 3"

            await host.execute_raw(f"rm -f {tmp_path}")
            write_result = await host.write_file(tmp_path, content)
            self.assertIsInstance(write_result, SuccessfulToolResult)

            read_result = await host.read_file(tmp_path)
            self.assertIsInstance(read_result, FileContentToolResult)
            self.assertEqual(read_result.content, content)
        finally:
            if pty_proc.returncode is None:
                await pty_proc.kill()

    async def test_replace_file_content(self) -> None:
        result = await self._connect_bash_host()
        if result is None:
            self.skipTest("Failed to create/connect bash host (CI environment)")
        host, pty_proc = result

        try:
            tmp_path = "/tmp/linhai_bash_e2e_replace_test.txt"
            original = "aaa bbb ccc\naaa ddd eee"
            await host.execute_raw(f"rm -f {tmp_path}")
            await host.write_file(tmp_path, original)

            replace_result = await host.replace_file_content(
                tmp_path, "bbb", "REPLACED"
            )
            self.assertIsInstance(replace_result, SuccessfulToolResult)

            read_result = await host.read_file(tmp_path)
            self.assertIsInstance(read_result, FileContentToolResult)
            self.assertEqual(read_result.content, "aaa REPLACED ccc\naaa ddd eee")
        finally:
            if pty_proc.returncode is None:
                await pty_proc.kill()

    async def test_read_large_file(self) -> None:
        result = await self._connect_bash_host()
        if result is None:
            self.skipTest("Failed to create/connect bash host (CI environment)")
        host, pty_proc = result

        try:
            repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
            large_file_path = repo_root / LARGE_FILE_RELATIVE
            if not large_file_path.exists():
                self.skipTest(f"Large file not found: {large_file_path}")

            file_size = large_file_path.stat().st_size
            self.assertGreater(file_size, 30 * 1024)

            expected_content = large_file_path.read_text(encoding="utf-8")

            read_result = await host.read_file(str(large_file_path))
            self.assertIsInstance(read_result, FileContentToolResult)
            self.assertEqual(read_result.content, expected_content)
        finally:
            if pty_proc.returncode is None:
                await pty_proc.kill()


if __name__ == "__main__":
    unittest.main()
