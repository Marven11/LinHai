import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.machine_control.process import (
    ProcessWriteResult,
    ProcessReadResult,
    ProcessKillResult,
    ProcessWaitResult,
)
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class _FakeProcess:
    def __init__(self):
        self._pid = "123"
        self._write_history = []
        self._responses = []
        self._read_index = 0

    @property
    def pid(self) -> str:
        return self._pid

    def add_response(self, data: str):
        self._responses.append(data)

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        self._write_history.append((content, with_enter))
        return ProcessWriteResult(pid=self._pid, success=True)

    async def stdio_read(
        self, wait_seconds: float, unescape_ansi: bool = True
    ) -> ProcessReadResult:
        if self._read_index < len(self._responses):
            data = self._responses[self._read_index]
            self._read_index += 1
            return ProcessReadResult(pid=self._pid, success=True, stdout=data)
        return ProcessReadResult(
            pid=self._pid, success=True, stdout="", exit_note="进程已退出"
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        return ProcessWaitResult(pid=self._pid, success=True, returncode=0)

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        return ProcessKillResult(pid=self._pid, success=True)


def _make_registry():
    registry = Mock(spec=Registry)
    registry.send_if_exists = AsyncMock()
    task_supervisor = AsyncMock()
    registry.has_member = Mock(return_value=True)
    registry.get_member_typechecked = Mock(return_value=task_supervisor)
    return registry, task_supervisor


class TestTrojanTransportConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_create_without_process(self):
        registry, _ = _make_registry()
        transport = TrojanTransport(registry)
        self.assertIsNone(transport._process)
        self.assertIsNone(transport._line_reader)

    async def test_create_with_process(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process)
        self.assertIsNotNone(transport._process)
        self.assertIsNotNone(transport._line_reader)


class TestTrojanTransportRequest(unittest.IsolatedAsyncioTestCase):
    async def test_send_request_writes_to_process(self):
        registry, task_supervisor = _make_registry()
        process = _FakeProcess()
        process.add_response('{"jsonrpc":"2.0","id":"abc","result":{}}\n')
        transport = TrojanTransport(registry, process=process)

        with self.assertRaises(ConnectionError):
            await transport._send_request("test", {})

    async def test_send_request_not_connected_raises(self):
        registry, _ = _make_registry()
        transport = TrojanTransport(registry)
        with self.assertRaises(ConnectionError):
            await transport._send_request("test", {})


class TestTrojanTransportDisconnect(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_kills_process(self):
        registry, task_supervisor = _make_registry()
        task_supervisor.cancel = Mock()
        task_supervisor.wait = AsyncMock(side_effect=asyncio.CancelledError)
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process)
        await transport.disconnect()
        self.assertFalse(transport.is_connected())

    async def test_disconnect_without_reader(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process)
        await transport.disconnect()
        self.assertFalse(transport.is_connected())


class TestTrojanTransportFutures(unittest.IsolatedAsyncioTestCase):
    async def test_fail_pending_futures(self):
        registry, _ = _make_registry()
        transport = TrojanTransport(registry)
        future = asyncio.get_event_loop().create_future()
        transport._pending_futures["test_id"] = future
        transport._fail_pending_futures()
        self.assertTrue(future.done())
        with self.assertRaises(ConnectionError):
            future.result()

    async def test_is_connected_initially_true(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process)
        self.assertTrue(transport.is_connected())

    async def test_is_connected_false_after_disconnect(self):
        registry, _ = _make_registry()
        process = _FakeProcess()
        transport = TrojanTransport(registry, process=process)
        await transport.disconnect()
        self.assertFalse(transport.is_connected())

    async def test_set_process_updates_state(self):
        registry, _ = _make_registry()
        transport = TrojanTransport(registry)
        transport._connection_valid = False
        process = _FakeProcess()
        transport.set_process(process)
        self.assertTrue(transport.is_connected())
        self.assertIsNotNone(transport._line_reader)


class TestSshHostUploadWithTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_upload_uses_task_supervisor(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = SshMachineControl("host", registry)
        call_count = 0

        async def mock_call_tool(name, args):
            nonlocal call_count
            call_count += 1
            if name == "create_temp_dir":
                return ToolResultSuccess(content="/tmp/upload")
            if name == "upload_chunk":
                return ToolResultSuccess(content="ok")
            if name == "concatenate_files":
                return ToolResultSuccess(content="done")
            if name == "remove_path":
                return ToolResultSuccess(content="removed")
            return ToolResultFailed(content="unknown")

        control.call_tool = mock_call_tool
        data = b"x" * 100
        result = await control.upload_file_concurrent(data, "/remote/path")
        self.assertIsInstance(result, ToolResultSuccess)
        self.assertGreater(call_count, 3)

    async def test_download_uses_task_supervisor(self):
        import base64
        import tempfile
        import os
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = SshMachineControl("host", registry)
        test_data = b"y" * 100

        async def mock_call_tool(name, args):
            if name == "get_file_size":
                return ToolResultSuccess(content=str(len(test_data)))
            if name == "download_chunk":
                return ToolResultSuccess(content=base64.b64encode(test_data).decode())
            return ToolResultFailed(content="unknown")

        control.call_tool = mock_call_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "out.bin")
            result = await control.download_file_concurrent("/remote/path", dest)
            self.assertIsInstance(result, ToolResultSuccess)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), test_data)


class TestSshHostUploadFailure(unittest.IsolatedAsyncioTestCase):
    async def test_upload_chunk_failure_propagates(self):
        from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
        from linhai.task_supervisor import PlainTaskSupervisor

        registry = Registry()
        registry.register_member("task_supervisor", PlainTaskSupervisor())
        control = SshMachineControl("host", registry)

        async def mock_call_tool(name, args):
            if name == "create_temp_dir":
                return ToolResultSuccess(content="/tmp/upload")
            if name == "upload_chunk":
                return ToolResultFailed(content="upload failed")
            if name == "remove_path":
                return ToolResultSuccess(content="removed")
            return ToolResultFailed(content="unknown")

        control.call_tool = mock_call_tool
        with self.assertRaises(RuntimeError):
            await control.upload_file_concurrent(b"x" * 100, "/remote/path")
