import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.machine_control.process import (
    ProcessWriteResult,
    ProcessReadResult,
    ProcessKillResult,
    ProcessWaitResult,
    ProcessIOError,
)
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


class _FakeProcess:
    def __init__(self):
        self._pid = "123"
        self._write_history: list[tuple[str, bool]] = []
        self._responses: list[str] = []
        self._read_index = 0
        self._write_should_fail = False
        self._kill_should_fail = False
        self._wait_timeout = False

    @property
    def pid(self) -> str:
        return self._pid

    def add_fragmented_response(self, *fragments: str) -> None:
        for fragment in fragments:
            self._responses.append(fragment)

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult | ProcessIOError:
        if self._write_should_fail:
            return ProcessIOError(error="写入失败")
        self._write_history.append((content, with_enter))
        return ProcessWriteResult(pid=self._pid, success=True)

    async def stdio_read(self, wait_seconds: float) -> ProcessReadResult:
        if self._read_index < len(self._responses):
            data = self._responses[self._read_index]
            self._read_index += 1
            return ProcessReadResult(
                pid=self._pid, success=True, stdout=data.encode("utf-8")
            )
        return ProcessReadResult(
            pid=self._pid, success=True, stdout=b"", exit_note="进程已退出"
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        if self._wait_timeout:
            return ProcessWaitResult(pid=self._pid, success=False, error="timeout")
        return ProcessWaitResult(pid=self._pid, success=True, returncode=0)

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        if self._kill_should_fail:
            return ProcessKillResult(pid=self._pid, success=False, error="kill failed")
        return ProcessKillResult(pid=self._pid, success=True)


def _make_registry() -> tuple[Mock, Mock]:
    registry = Mock(spec=Registry)
    registry.send_if_exists = AsyncMock()
    task_supervisor = AsyncMock()
    registry.has_member = Mock(return_value=True)
    registry.get_member_typechecked = Mock(return_value=task_supervisor)
    return registry, task_supervisor


class TestTrojanTransportRequest(unittest.IsolatedAsyncioTestCase):
    async def test_send_request_not_connected_raises(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        transport._connection_valid = False
        with self.assertRaises(ConnectionError):
            await transport._send_request("test", {})


class TestTrojanTransportDisconnect(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_kills_process(self):
        registry, task_supervisor = _make_registry()
        task_supervisor.cancel = Mock()
        task_supervisor.wait = AsyncMock(side_effect=asyncio.CancelledError)
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        await transport.disconnect()
        self.assertFalse(transport.is_connected())

    async def test_disconnect_without_reader(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        await transport.disconnect()
        self.assertFalse(transport.is_connected())

    async def test_disconnect_fails_pending_futures(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        future = asyncio.get_event_loop().create_future()
        transport._pending_futures["req_1"] = future
        await transport.disconnect()
        self.assertTrue(future.done())
        with self.assertRaises(ConnectionError):
            future.result()


class TestTrojanTransportFutures(unittest.IsolatedAsyncioTestCase):
    async def test_fail_pending_futures_single(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        future = asyncio.get_event_loop().create_future()
        transport._pending_futures["test_id"] = future
        transport._fail_pending_futures()
        self.assertTrue(future.done())
        with self.assertRaises(ConnectionError):
            future.result()

    async def test_fail_pending_futures_multiple(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        f1 = asyncio.get_event_loop().create_future()
        f2 = asyncio.get_event_loop().create_future()
        transport._pending_futures["a"] = f1
        transport._pending_futures["b"] = f2
        transport._fail_pending_futures()
        self.assertTrue(f1.done())
        self.assertTrue(f2.done())
        with self.assertRaises(ConnectionError):
            f1.result()
        with self.assertRaises(ConnectionError):
            f2.result()
        self.assertEqual(len(transport._pending_futures), 0)


class TestSshHostUploadWithTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_upload_uses_task_supervisor(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = PosixShellControl(registry=registry)
        call_count = 0

        async def mock_call_tool(
            name: str, args: dict
        ) -> SuccessfulToolResult | FailedToolResult:
            nonlocal call_count
            call_count += 1
            if name == "create_temp_dir":
                return SuccessfulToolResult(content="/tmp/upload")
            if name == "upload_chunk":
                return SuccessfulToolResult(content="ok")
            if name == "concatenate_files":
                return SuccessfulToolResult(content="done")
            if name == "remove_path":
                return SuccessfulToolResult(content="removed")
            return FailedToolResult(content="unknown")

        control.call_tool = mock_call_tool
        data = b"x" * 100
        result = await control.upload_file_concurrent(data, "/remote/path")
        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertGreater(call_count, 3)

    async def test_download_uses_task_supervisor(self):
        import base64
        import tempfile
        import os
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = PosixShellControl(registry=registry)
        test_data = b"y" * 100

        async def mock_call_tool(
            name: str, args: dict
        ) -> SuccessfulToolResult | FailedToolResult:
            if name == "get_file_size":
                return SuccessfulToolResult(content=str(len(test_data)))
            if name == "download_chunk":
                return SuccessfulToolResult(
                    content=base64.b64encode(test_data).decode()
                )
            return FailedToolResult(content="unknown")

        control.call_tool = mock_call_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "out.bin")
            result = await control.download_file_concurrent("/remote/path", dest)
            self.assertIsInstance(result, SuccessfulToolResult)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), test_data)


class TestSshHostUploadFailure(unittest.IsolatedAsyncioTestCase):
    async def test_upload_chunk_failure_propagates(self):
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = PosixShellControl(registry=registry)

        async def mock_call_tool(
            name: str, args: dict
        ) -> SuccessfulToolResult | FailedToolResult:
            if name == "create_temp_dir":
                return SuccessfulToolResult(content="/tmp/upload")
            if name == "upload_chunk":
                return FailedToolResult(content="upload failed")
            if name == "remove_path":
                return SuccessfulToolResult(content="removed")
            return FailedToolResult(content="unknown")

        control.call_tool = mock_call_tool
        with self.assertRaises(RuntimeError):
            await control.upload_file_concurrent(b"x" * 100, "/remote/path")

    async def test_download_base64_corruption_raises(self):
        import tempfile
        import os
        from linhai.machine_control.posix_shell.posix_shell_control import (
            PosixShellControl,
        )
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = PosixShellControl(registry=registry)

        async def mock_call_tool(
            name: str, args: dict
        ) -> SuccessfulToolResult | FailedToolResult:
            if name == "get_file_size":
                return SuccessfulToolResult(content="10")
            if name == "download_chunk":
                return SuccessfulToolResult(content="!!!not-base64!!!")
            return FailedToolResult(content="unknown")

        control.call_tool = mock_call_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "out.bin")
            with self.assertRaises(Exception):
                await control.download_file_concurrent("/remote/path", dest)


class TestFakeProcessEdgeCases(unittest.TestCase):
    def test_kill_failure(self):
        proc = _FakeProcess()
        proc._kill_should_fail = True
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(proc.kill())
            self.assertFalse(result.success)
        finally:
            loop.close()

    def test_wait_timeout(self):
        proc = _FakeProcess()
        proc._wait_timeout = True
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(proc.wait(1.0))
            self.assertFalse(result.success)
        finally:
            loop.close()

    def test_fragmented_stdout_reads(self):
        proc = _FakeProcess()
        proc.add_fragmented_response("chunk1\n", "chunk2\n", "final\n")
        loop = asyncio.new_event_loop()
        try:
            r1 = loop.run_until_complete(proc.stdio_read(1.0))
            self.assertEqual(r1.stdout, b"chunk1\n")
            r2 = loop.run_until_complete(proc.stdio_read(1.0))
            self.assertEqual(r2.stdout, b"chunk2\n")
            r3 = loop.run_until_complete(proc.stdio_read(1.0))
            self.assertEqual(r3.stdout, b"final\n")
            r4 = loop.run_until_complete(proc.stdio_read(1.0))
            self.assertEqual(r4.exit_note, "进程已退出")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
