import asyncio
import shutil
import unittest

from linhai.machine_control.bash_host import BashHostControl
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import SuccessfulToolResult
from tests.test_helpers import _AsyncioProcessAdapter


class TestBashHostControlE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_bash_process(
        self,
    ) -> tuple[_AsyncioProcessAdapter, asyncio.subprocess.Process]:
        bash_path = shutil.which("bash") or shutil.which("sh")
        if bash_path is None:
            self.skipTest("bash/sh not found")
        process = await asyncio.create_subprocess_exec(
            bash_path,
            "-s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        return _AsyncioProcessAdapter(process), process

    async def _create_control(
        self,
    ) -> tuple[BashHostControl, _AsyncioProcessAdapter, asyncio.subprocess.Process]:
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = BashHostControl(registry)
        adapter, process = await self._create_bash_process()
        return control, adapter, process

    async def _cleanup(self, process: asyncio.subprocess.Process) -> None:
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        process.kill()
        await process.wait()

    async def test_connect_and_ping(self):
        control, adapter, process = await self._create_control()
        result = await control.connect(adapter)
        self.assertTrue(result)
        try:
            ping_result = await control.ping()
            self.assertIsInstance(
                ping_result, SuccessfulToolResult, f"ping failed: {ping_result}"
            )
        finally:
            await self._cleanup(process)

    async def test_execute_raw_basic_commands(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            rc, stdout, stderr = await control.execute_raw("echo test_output")
            self.assertEqual(rc, 0)
            self.assertIn("test_output", stdout)
            rc, stdout, stderr = await control.execute_raw("false")
            self.assertNotEqual(rc, 0)
        finally:
            await self._cleanup(process)

    async def test_create_process_echo_and_wait(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(["echo", "hello_world"])
            self.assertTrue(result.success, f"create_process failed: {result.error}")
            self.assertIsNotNone(result.pid)
            self.assertTrue(len(result.pid) > 0)

            proc = control.get_process(result.pid)
            self.assertIsNotNone(proc)

            wait_result = await proc.wait(timeout=10.0)
            self.assertTrue(wait_result.success, f"wait failed: {wait_result.error}")
            self.assertEqual(wait_result.returncode, 0)
            self.assertIn("hello_world", wait_result.stdout)
        finally:
            await self._cleanup(process)

    async def test_create_process_returns_immediately_for_fast_commands(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(["echo", "fast"], wait_second=2.0)
            self.assertTrue(result.success, f"create_process failed: {result.error}")
            self.assertIsNotNone(result.returncode)
            self.assertEqual(result.returncode, 0)
            self.assertIn("fast", result.stdout)
        finally:
            await self._cleanup(process)

    async def test_create_process_nonzero_exit(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(
                ["sh", "-c", "echo err_msg >&2; exit 42"]
            )
            self.assertTrue(result.success, f"create_process failed: {result.error}")

            proc = control.get_process(result.pid)
            self.assertIsNotNone(proc)

            wait_result = await proc.wait(timeout=10.0)
            self.assertTrue(wait_result.success)
            self.assertEqual(wait_result.returncode, 42)
            self.assertIn("err_msg", wait_result.stderr)
        finally:
            await self._cleanup(process)

    async def test_stdio_read_captures_output(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(
                ["sh", "-c", "echo hello; echo world"],
                wait_second=2.0,
            )
            self.assertTrue(result.success, f"create_process failed: {result.error}")

            proc = control.get_process(result.pid)
            self.assertIsNotNone(proc)

            read_result = await proc.stdio_read(wait_seconds=2.0)
            self.assertTrue(read_result.success)
            self.assertIn(b"hello", read_result.stdout)
            self.assertIn(b"world", read_result.stdout)
        finally:
            await self._cleanup(process)

    async def test_list_process_pids(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result1 = await control.create_process(["sleep", "60"])
            self.assertTrue(result1.success, f"create_process1 failed: {result1.error}")
            result2 = await control.create_process(["sleep", "60"])
            self.assertTrue(result2.success, f"create_process2 failed: {result2.error}")

            pids = control.list_process_pids()
            self.assertIn(result1.pid, pids)
            self.assertIn(result2.pid, pids)
            self.assertGreaterEqual(len(pids), 2)

            proc1 = control.get_process(result1.pid)
            self.assertIsNotNone(proc1)
            await proc1.kill()

            proc2 = control.get_process(result2.pid)
            self.assertIsNotNone(proc2)
            await proc2.kill()
        finally:
            await self._cleanup(process)

    async def test_kill_process(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(["sleep", "300"])
            self.assertTrue(result.success, f"create_process failed: {result.error}")

            proc = control.get_process(result.pid)
            self.assertIsNotNone(proc)

            kill_result = await proc.kill(graceful=True)
            self.assertTrue(kill_result.success, f"kill failed: {kill_result.error}")

            await asyncio.sleep(0.5)
            pid = result.pid
            rc_check = await control.execute_raw(
                f"if kill -0 {pid} 2>/dev/null; then "
                f"if grep -qs '^State:.*Z' /proc/{pid}/status 2>/dev/null; then "
                f"echo DEAD; else echo ALIVE; fi; else echo DEAD; fi"
            )
            self.assertEqual(rc_check[0], 0)
            self.assertIn("DEAD", rc_check[1])
        finally:
            await self._cleanup(process)

    async def test_kill_process_force(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            result = await control.create_process(["sleep", "300"])
            self.assertTrue(result.success, f"create_process failed: {result.error}")

            proc = control.get_process(result.pid)
            self.assertIsNotNone(proc)

            kill_result = await proc.kill(graceful=False)
            self.assertTrue(kill_result.success, f"kill failed: {kill_result.error}")

            await asyncio.sleep(0.5)
            pid = result.pid
            rc_check = await control.execute_raw(
                f"if kill -0 {pid} 2>/dev/null; then "
                f"if grep -qs '^State:.*Z' /proc/{pid}/status 2>/dev/null; then "
                f"echo DEAD; else echo ALIVE; fi; else echo DEAD; fi"
            )
            self.assertEqual(rc_check[0], 0)
            self.assertIn("DEAD", rc_check[1])
        finally:
            await self._cleanup(process)


if __name__ == "__main__":
    unittest.main()
