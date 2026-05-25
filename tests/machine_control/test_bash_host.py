import asyncio
import base64
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.bash_host.process import BashProcess
from linhai.machine_control.process import (
    ProcessCreateResult,
    ProcessKillResult,
    ProcessReadResult,
    ProcessWaitResult,
    ProcessWriteResult,
)
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


class TestBashProcess(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.host = Mock(spec=BashHostControl)

    def tearDown(self):
        self.loop.close()

    def test_pid_property(self):
        proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
        self.assertEqual(proc.pid, "123")

    def test_returncode_always_none(self):
        proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
        self.assertIsNone(proc.returncode)

    def test_stdio_write_success(self):
        async def test():
            self.host.execute_raw = AsyncMock(return_value=(0, "", ""))
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.stdio_write("hello", with_enter=True)
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "123")

        self.loop.run_until_complete(test())

    def test_stdio_write_failure(self):
        async def test():
            self.host.execute_raw = AsyncMock(return_value=(1, "", "write error"))
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.stdio_write("hello", with_enter=False)
            self.assertFalse(result.success)
            self.assertEqual(result.error, "write error")

        self.loop.run_until_complete(test())

    def test_stdio_read_returns_decoded_data(self):
        async def test():
            stdout_b64 = base64.b64encode(b"hello").decode()
            stderr_b64 = base64.b64encode(b"world").decode()
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, stdout_b64, ""),
                    (0, "5", ""),
                    (0, stderr_b64, ""),
                    (0, "5", ""),
                ]
            )
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.stdio_read(wait_seconds=1.0)
            self.assertTrue(result.success)
            self.assertEqual(result.stdout, b"hello")
            self.assertEqual(result.stderr, b"world")

        self.loop.run_until_complete(test())

    def test_stdio_read_empty(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "0", ""),
                    (0, "", ""),
                    (0, "0", ""),
                ]
            )
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.stdio_read(wait_seconds=1.0)
            self.assertTrue(result.success)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(result.stderr, b"")

        self.loop.run_until_complete(test())

    def test_wait_returns_on_exit(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "0", ""),
                    (0, "output", ""),
                    (0, "errors", ""),
                ]
            )
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.wait(timeout=5.0)
            self.assertTrue(result.success)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "output")
            self.assertEqual(result.stderr, "errors")

        self.loop.run_until_complete(test())

    def test_wait_timeout(self):
        async def test():
            self.host.execute_raw = AsyncMock(return_value=(0, "NONE", ""))
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.wait(timeout=0.5)
            self.assertTrue(result.success)
            self.assertIsNone(result.returncode)

        self.loop.run_until_complete(test())

    def test_kill_graceful(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "DEAD", ""),
                ]
            )
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.kill(graceful=True)
            self.assertTrue(result.success)
            call_args = self.host.execute_raw.call_args_list[0][0][0]
            self.assertIn("TERM", call_args)

        self.loop.run_until_complete(test())

    def test_kill_force(self):
        async def test():
            self.host.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "DEAD", ""),
                ]
            )
            proc = BashProcess(pid="123", proc_dir="/tmp/proc_1", host=self.host)
            result = await proc.kill(graceful=False)
            self.assertTrue(result.success)
            first_call = self.host.execute_raw.call_args_list[0][0][0]
            self.assertIn("-9", first_call)

        self.loop.run_until_complete(test())


class TestBashHostControlProcessMgmt(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.has_member = Mock(return_value=False)
        self.registry.members = {}
        self.control = BashHostControl(registry=self.registry)

    def tearDown(self):
        self.loop.close()

    def test_get_process_empty(self):
        result = self.control.get_process("999")
        self.assertIsNone(result)

    def test_list_process_pids_empty(self):
        result = self.control.list_process_pids()
        self.assertEqual(result, [])

    def test_create_process_dir_failure(self):
        async def test():
            self.control.execute_raw = AsyncMock(return_value=(1, "", "mkdir failed"))
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(["echo", "hello"])
            self.assertFalse(result.success)
            self.assertIn("创建进程目录失败", result.error)

        self.loop.run_until_complete(test())

    def test_create_process_start_failure(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (1, "", "start failed"),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(["echo", "hello"])
            self.assertFalse(result.success)
            self.assertIn("启动进程失败", result.error)

        self.loop.run_until_complete(test())

    def test_create_process_invalid_pid(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "not_a_pid", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(["echo", "hello"])
            self.assertFalse(result.success)
            self.assertIn("无法解析进程ID", result.error)

        self.loop.run_until_complete(test())

    def test_create_process_success_still_running(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "42", ""),
                    (0, "NONE", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(
                ["echo", "hello"], wait_second=0.0
            )
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "42")
            self.assertIsNone(result.returncode)
            self.assertIn("42", self.control.list_process_pids())

        self.loop.run_until_complete(test())

    def test_create_process_already_exited(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "42", ""),
                    (0, "0", ""),
                    (0, "hello output", ""),
                    (0, "", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            result = await self.control.create_process(
                ["echo", "hello"], wait_second=0.01
            )
            self.assertTrue(result.success)
            self.assertEqual(result.pid, "42")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "hello output")

        self.loop.run_until_complete(test())

    def test_get_process_after_create(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "42", ""),
                ]
            )
            self.control._tmp_dir = "/tmp/test"
            await self.control.create_process(["echo", "hello"], wait_second=0.0)
            proc = self.control.get_process("42")
            self.assertIsNotNone(proc)
            self.assertEqual(proc.pid, "42")

        self.loop.run_until_complete(test())


class TestBashHostChangeDirectory(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.has_member = Mock(return_value=False)
        self.registry.members = {}
        self.control = BashHostControl(registry=self.registry)
        self.control._cwd = "/home/user"

    def tearDown(self):
        self.loop.close()

    def test_change_directory_success(self):
        async def test():
            self.control.execute_raw = AsyncMock(return_value=(0, "/tmp", ""))
            result = await self.control.change_directory("/tmp")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertEqual(self.control._cwd, "/tmp")
            self.assertIn("/tmp", result.content)

        self.loop.run_until_complete(test())

    def test_change_directory_failure(self):
        async def test():
            self.control.execute_raw = AsyncMock(
                return_value=(1, "", "not a directory")
            )
            result = await self.control.change_directory("/no/such/dir")
            self.assertIsInstance(result, FailedToolResult)
            self.assertEqual(self.control._cwd, "/home/user")

        self.loop.run_until_complete(test())


class TestBashHostDownloadUpload(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.has_member = Mock(return_value=False)
        self.registry.members = {}
        self.control = BashHostControl(registry=self.registry)
        self.control._tmp_dir = "/tmp/linhai_test"
        self.control._cwd = "/home/user"

    def tearDown(self):
        self.loop.close()

    def test_download_file_not_exist(self):
        async def test():
            self.control.execute_raw = AsyncMock(return_value=(1, "", ""))
            result = await self.control.download_file_concurrent(
                "/no/file", "/tmp/local"
            )
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("不存在", result.content)

        self.loop.run_until_complete(test())

    def test_download_small_file(self):
        async def test():
            content = b"hello world"
            b64_content = base64.b64encode(content).decode("ascii")
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, str(len(content)), ""),
                    (0, b64_content, ""),
                ]
            )
            with tempfile.NamedTemporaryFile(delete=False) as f:
                local_path = f.name
            try:
                result = await self.control.download_file_concurrent(
                    "/remote/file", local_path
                )
                self.assertIsInstance(result, SuccessfulToolResult)
                with open(local_path, "rb") as f:
                    self.assertEqual(f.read(), content)
            finally:
                os.unlink(local_path)

        self.loop.run_until_complete(test())

    def test_upload_file_success(self):
        async def test():
            data = b"test data for upload"
            self.control.execute_raw = AsyncMock(
                side_effect=[
                    (0, "", ""),
                    (0, "", ""),
                    (0, "", ""),
                ]
            )
            result = await self.control.upload_file_concurrent(
                data, "/remote/path/file.txt"
            )
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("上传", result.content)

        self.loop.run_until_complete(test())

    def test_upload_file_dir_not_exist(self):
        async def test():
            self.control.execute_raw = AsyncMock(return_value=(1, "", ""))
            result = await self.control.upload_file_concurrent(
                b"data", "/no/dir/file.txt"
            )
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("目录不存在", result.content)

        self.loop.run_until_complete(test())


class TestBashHostExecuteLock(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.registry = Mock(spec=Registry)
        self.registry.send_if_exists = AsyncMock()
        self.registry.has_member = Mock(return_value=False)
        self.registry.members = {}
        self.control = BashHostControl(registry=self.registry)

    def tearDown(self):
        self.loop.close()

    def test_has_execute_lock(self):
        self.assertIsInstance(self.control._execute_lock, asyncio.Lock)

    def test_execute_lock_serializes_concurrent_calls(self):
        async def test():
            concurrent_count = 0
            max_concurrent = 0
            mock_process = AsyncMock()

            async def mock_write(content, with_enter):
                return Mock(success=True)

            async def tracked_read(wait_seconds=1.0):
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                marker = f"_LINHAI_CMD_RESULT_{self.control._counter}"
                await asyncio.sleep(0.05)
                concurrent_count -= 1
                return Mock(success=True, stdout=f"{marker}:0\n".encode())

            mock_process.stdio_write = mock_write
            mock_process.stdio_read = tracked_read
            self.control._shell_process = mock_process

            await asyncio.gather(
                self.control.execute_raw("cmd1"),
                self.control.execute_raw("cmd2"),
                self.control.execute_raw("cmd3"),
            )

            self.assertEqual(
                max_concurrent,
                1,
                f"Expected max 1 concurrent call, got {max_concurrent}",
            )

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
