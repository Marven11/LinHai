import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.machine_control.trojan.transport import TrojanTransport
from linhai.machine_control.ssh_host.ssh_host import SshMachineControl
from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


def _make_registry() -> Registry:
    registry = Registry()
    registry.register_member("task_supervisor", PlainTaskSupervisor())
    return registry


class TestTrojanTransportTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_start_reading_uses_task_supervisor(self):
        registry = _make_registry()
        transport = TrojanTransport(registry)
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=[b"\n", asyncio.CancelledError()])
        transport.stdout = mock_stdout
        transport.start_reading()
        self.assertTrue(transport._reader_started)
        task_supervisor = registry.get_member_typechecked(
            "task_supervisor", PlainTaskSupervisor
        )
        task_supervisor.cancel("trojan_transport_reader")
        await asyncio.sleep(0.05)

    async def test_start_reading_idempotent(self):
        registry = _make_registry()
        transport = TrojanTransport(registry)
        transport.stdout = AsyncMock()
        transport.stdout.readline = AsyncMock(return_value=b"\n")
        transport.start_reading()
        transport.start_reading()
        self.assertTrue(transport._reader_started)
        task_supervisor = registry.get_member_typechecked(
            "task_supervisor", PlainTaskSupervisor
        )
        task_supervisor.cancel("trojan_transport_reader")
        await asyncio.sleep(0.05)

    async def test_disconnect_cancels_reader(self):
        registry = _make_registry()
        transport = TrojanTransport(registry)
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=asyncio.CancelledError)
        transport.stdout = mock_stdout
        transport.start_reading()
        await transport.disconnect()
        self.assertFalse(transport._connection_valid)

    async def test_disconnect_without_reader(self):
        registry = _make_registry()
        transport = TrojanTransport(registry)
        mock_process = MagicMock()
        mock_process.wait = AsyncMock(return_value=None)
        transport.process = mock_process
        await transport.disconnect()
        self.assertFalse(transport._connection_valid)

    async def test_wait_for_disconnect(self):
        registry = _make_registry()
        transport = TrojanTransport(registry)
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(return_value=b"")
        transport.stdout = mock_stdout
        transport.start_reading()
        await asyncio.sleep(0.05)
        await transport.wait_for_disconnect()


class TestSshHostUploadWithTaskSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_upload_uses_task_supervisor(self):
        registry = _make_registry()
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

        registry = _make_registry()
        control = SshMachineControl("host", registry)
        test_data = b"y" * 100

        async def mock_call_tool(name, args):
            if name == "get_file_size":
                return ToolResultSuccess(content=str(len(test_data)))
            if name == "download_chunk":
                return ToolResultSuccess(content=base64.b64encode(test_data).decode())
            return ToolResultFailed(content="unknown")

        control.call_tool = mock_call_tool
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "out.bin")
            result = await control.download_file_concurrent("/remote/path", dest)
            self.assertIsInstance(result, ToolResultSuccess)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), test_data)


class TestSshHostUploadFailure(unittest.IsolatedAsyncioTestCase):
    async def test_upload_chunk_failure_propagates(self):
        registry = _make_registry()
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


if __name__ == "__main__":
    unittest.main()
