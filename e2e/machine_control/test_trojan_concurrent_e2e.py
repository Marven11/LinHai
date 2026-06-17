import asyncio
import shutil
import time
import unittest

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import SuccessfulToolResult
from tests.test_helpers import _AsyncioProcessAdapter


class TestTrojanConcurrentE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_control(
        self,
    ) -> tuple[PosixShellControl, _AsyncioProcessAdapter, asyncio.subprocess.Process]:
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = PosixShellControl(registry=registry)

        bash_path = shutil.which("bash") or shutil.which("sh")
        assert bash_path is not None, "bash/sh not found"

        process = await asyncio.create_subprocess_exec(
            bash_path,
            "-s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )

        adapter = _AsyncioProcessAdapter(process)
        return control, adapter, process

    async def _cleanup(self, process: asyncio.subprocess.Process) -> None:
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        if process.returncode is None:
            process.kill()
            await process.wait()

    async def test_concurrent_ping_and_read_file(self):
        control, adapter, process = await self._create_control()
        connected = await control.connect(adapter)
        self.assertTrue(connected, "连接posix shell失败")

        large_file = "linhai/machine_control/trojan/trojan.py"

        try:
            ping_count = 0
            ping_errors: list[str] = []
            stop_event = asyncio.Event()

            async def heartbeat():
                nonlocal ping_count
                while not stop_event.is_set():
                    try:
                        result = await control.ping()
                        if not isinstance(result, SuccessfulToolResult):
                            ping_errors.append(f"ping失败: {result}")
                        ping_count += 1
                    except Exception as e:
                        ping_errors.append(f"ping异常: {e}")
                    await asyncio.sleep(1.0)

            heartbeat_task = asyncio.create_task(heartbeat())

            start = time.monotonic()
            read_count = 0
            read_errors: list[str] = []

            while time.monotonic() - start < 60.0:
                try:
                    result = await control.read_file(large_file)
                    if isinstance(result, SuccessfulToolResult):
                        if len(result.content) < 10000:
                            read_errors.append(
                                f"read_file too small: {len(result.content)}"
                            )
                        read_count += 1
                    else:
                        read_errors.append(f"read_file failed: {result}")
                except Exception as e:
                    read_errors.append(f"read_file异常: {e}")

                await asyncio.sleep(0.5)

            stop_event.set()
            await asyncio.wait_for(heartbeat_task, timeout=10.0)

            self.assertGreater(
                read_count, 10, f"读取次数过少: {read_count}, 错误: {read_errors}"
            )
            self.assertEqual(len(read_errors), 0, f"读取错误: {read_errors}")
            self.assertGreater(
                ping_count, 0, f"ping次数过少: {ping_count}, 错误: {ping_errors}"
            )
            self.assertEqual(len(ping_errors), 0, f"ping错误: {ping_errors}")
        finally:
            await control.disconnect()
            await self._cleanup(process)


if __name__ == "__main__":
    unittest.main()
