import asyncio
import shutil
import unittest

from linhai.machine_control.bash_host import BashHostControl
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import ToolResultSuccess
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
                ping_result, ToolResultSuccess, f"ping failed: {ping_result}"
            )
        finally:
            await self._cleanup(process)

    async def test_two_bash_simultaneous_operations(self):
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control1, adapter1, proc1 = await self._create_control()
        control2, adapter2, proc2 = await self._create_control()
        connected1 = await control1.connect(adapter1)
        connected2 = await control2.connect(adapter2)
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        try:
            results = await asyncio.gather(control1.ping(), control2.ping())
            self.assertIsInstance(
                results[0], ToolResultSuccess, f"ping1 failed: {results[0]}"
            )
            self.assertIsInstance(
                results[1], ToolResultSuccess, f"ping2 failed: {results[1]}"
            )
            echo_results = await asyncio.gather(
                control1._execute_raw("echo hello_from_1"),
                control2._execute_raw("echo hello_from_2"),
            )
            rc1, stdout1, stderr1 = echo_results[0]
            rc2, stdout2, stderr2 = echo_results[1]
            self.assertEqual(rc1, 0, f"echo1 failed: rc={rc1}, stderr={stderr1}")
            self.assertEqual(rc2, 0, f"echo2 failed: rc={rc2}, stderr={stderr2}")
            self.assertIn("hello_from_1", stdout1)
            self.assertIn("hello_from_2", stdout2)
        finally:
            await self._cleanup(proc1)
            await self._cleanup(proc2)

    async def test_execute_raw_basic_commands(self):
        control, adapter, process = await self._create_control()
        await control.connect(adapter)
        try:
            rc, stdout, stderr = await control._execute_raw("echo test_output")
            self.assertEqual(rc, 0)
            self.assertIn("test_output", stdout)
            rc, stdout, stderr = await control._execute_raw(
                "cat /etc/hostname || hostname"
            )
            self.assertEqual(rc, 0)
            self.assertTrue(len(stdout.strip()) > 0)
            rc, stdout, stderr = await control._execute_raw("false")
            self.assertNotEqual(rc, 0)
        finally:
            await self._cleanup(process)


if __name__ == "__main__":
    unittest.main()
