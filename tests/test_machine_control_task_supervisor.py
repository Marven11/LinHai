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
    def __init__(self, pid: str = "123"):
        self._pid = pid
        self._write_history: list[tuple[str, bool]] = []
        self._responses: list[bytes] = []
        self._read_index = 0
        self._read_fail: ProcessIOError | None = None
        self._killed = False
        self._kill_fails = False

    @property
    def pid(self) -> str:
        return self._pid

    def add_response_bytes(self, data: bytes):
        self._responses.append(data)

    def set_read_fail(self, error: ProcessIOError):
        self._read_fail = error

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        self._write_history.append((content, with_enter))
        return ProcessWriteResult(pid=self._pid, success=True)

    async def stdio_read(self, wait_seconds: float) -> ProcessReadResult:
        if self._read_fail is not None:
            return self._read_fail
        if self._read_index < len(self._responses):
            data = self._responses[self._read_index]
            self._read_index += 1
            return ProcessReadResult(pid=self._pid, success=True, stdout=data)
        return ProcessReadResult(
            pid=self._pid, success=True, stdout=b"", exit_note="进程已退出"
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        return ProcessWaitResult(pid=self._pid, success=True, returncode=0)

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        self._killed = True
        if self._kill_fails:
            return ProcessKillResult(pid=self._pid, success=False, error="kill failed")
        return ProcessKillResult(pid=self._pid, success=True)


def _make_registry():
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

    async def test_send_request_write_failure_raises(self):
        from linhai.machine_control.process import ProcessWriteResult

        registry, _ = _make_registry()
        process = _FakeProcess()
        fail_pid = "fail"

        async def fail_write(content: str, with_enter: bool):
            if content != "":
                raise ConnectionError("simulated write failure")
            return ProcessWriteResult(pid=fail_pid, success=True)

        process.stdio_write = fail_write
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        with self.assertRaises(ConnectionError):
            await transport._send_request("test", {"key": "value"})


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


class TestTrojanTransportFutures(unittest.IsolatedAsyncioTestCase):
    async def test_fail_pending_futures_sets_exception(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        future = asyncio.get_event_loop().create_future()
        transport._pending_futures["test_id"] = future
        transport._fail_pending_futures()
        self.assertTrue(future.done())
        with self.assertRaises(ConnectionError):
            future.result()
        self.assertEqual(len(transport._pending_futures), 0)

    async def test_send_request_returns_io_error_on_exception(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        transport._connection_valid = False
        result = await transport.send_request("test", {})
        self.assertIn("io_error", result)
        self.assertIn("连接已失效", result["io_error"])

    async def test_send_request_response_missing_result(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")

        async def mock_send(method, params):
            return {"jsonrpc": "2.0", "id": "x", "other": "data"}

        transport._send_request = mock_send

        result = await transport.send_request("test", {})
        self.assertIn("io_error", result)
        self.assertIn("缺少result", result["io_error"])

    async def test_send_request_with_error_in_response(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")

        async def mock_send(method, params):
            return {
                "jsonrpc": "2.0",
                "id": "x",
                "error": {"code": -1, "message": "模拟错误"},
            }

        transport._send_request = mock_send

        result = await transport.send_request("test", {})
        self.assertIn("io_error", result)
        self.assertIn("模拟错误", result["io_error"])


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

        async def mock_call_tool(name, args):
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

        async def mock_call_tool(name, args):
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

        async def mock_call_tool(name, args):
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


class TestTrojanTransportReadResponses(unittest.IsolatedAsyncioTestCase):
    async def test_read_responses_process_io_error_disconnects(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        process.set_read_fail(ProcessIOError(error="模拟IO错误"))
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        transport._reader_started = True
        await transport._read_responses()
        self.assertFalse(transport.is_connected())

    async def test_read_responses_empty_stdout_with_exit_note_disconnects(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        process.add_response_bytes(b"")
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        transport._connection_valid = True
        await transport._read_responses()
        self.assertFalse(transport.is_connected())

    async def test_read_responses_invalid_json_skips(self):
        import json
        from linhai.machine_control.trojan.transport import PulseEncoder

        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        transport._pulse_encoder = PulseEncoder(b"<linhai_pulse_fake>", 3000, False)
        transport._reader_started = True

        valid = json.dumps(
            {"jsonrpc": "2.0", "id": "req1", "result": {"ok": True}}
        ).encode()
        encoded = transport._pulse_encoder.encode(valid)
        process.add_response_bytes(encoded[0])

        invalid_data = b"<linhai_pulse_fake>{not json}<linhai_pulse_fake>"
        process.add_response_bytes(invalid_data)

        transport._connection_valid = False
        await transport._read_responses()

    async def test_disconnect_fails_pending_futures_with_connection_error(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process, marker_hex="abcd")
        future = asyncio.get_event_loop().create_future()
        transport._pending_futures["req1"] = future
        await transport.disconnect()
        self.assertTrue(future.done())
        with self.assertRaises(ConnectionError):
            future.result()
        self.assertTrue(process._killed)
