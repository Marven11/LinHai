import asyncio
import json
import unittest
import shutil
import tempfile
import os
from pathlib import Path

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from tests.test_helpers import _AsyncioProcessAdapter
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor


class TestPosixShellControlE2E(unittest.IsolatedAsyncioTestCase):
    async def _create_control_with_bash(
        self,
    ) -> tuple[PosixShellControl, _AsyncioProcessAdapter, asyncio.subprocess.Process]:
        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())

        control = PosixShellControl(
            host="localhost",
            registry=registry,
        )

        trojan_source = (
            Path(__file__).parent.parent.parent
            / "linhai"
            / "machine_control"
            / "trojan"
            / "trojan.py"
        )
        if not trojan_source.exists():
            self.skipTest(f"trojan.py不存在: {trojan_source}")

        # 使用which查找bash路径，提高跨平台兼容性
        bash_path = shutil.which("bash")
        if bash_path is None:
            # 如果找不到bash，尝试使用sh
            bash_path = shutil.which("sh")
            if bash_path is None:
                self.skipTest("未找到bash或sh命令")

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

    async def _cleanup_process(self, control, process):
        await control.close()
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        process.kill()
        await process.wait()
        process._transport.close()

    async def test_connect_with_local_bash(self):
        control, adapter, process = await self._create_control_with_bash()
        result = await control.connect(adapter)
        self.assertTrue(result)

        try:
            process_result = await control.create_process(["echo", "hello"])
            self.assertTrue(
                process_result.success,
                f"create_process failed: {getattr(process_result, 'error', 'unknown')}",
            )
            self.assertIn("hello", process_result.stdout)
        finally:
            await self._cleanup_process(control, process)

    async def test_call_tool_with_local_bash(self):
        control, adapter, process = await self._create_control_with_bash()
        result = await control.connect(adapter)
        self.assertTrue(result)

        try:
            from linhai.tool.base import ToolResultSuccess

            # 使用跨平台存在的文件路径
            # /etc/passwd 在Unix-like系统上都存在
            test_file = "/etc/passwd"

            # 如果/etc/passwd不存在，使用临时文件
            if not os.path.exists(test_file):
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
                    tmp.write("test content\n")
                    test_file = tmp.name

            tool_result = await control.call_tool("read_file", {"filepath": test_file})
            self.assertIsInstance(tool_result, ToolResultSuccess)

            # 清理临时文件
            if test_file.startswith(tempfile.gettempdir()):
                os.unlink(test_file)

        finally:
            await self._cleanup_process(control, process)


if __name__ == "__main__":
    unittest.main()
