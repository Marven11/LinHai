from __future__ import annotations

import asyncio
import json
from unittest.mock import Mock, AsyncMock

import pytest

from linhai.machine_control.process import (
    Process,
    ProcessCreateResult,
    ProcessStdioResult,
    ProcessWaitResult,
    ProcessKillResult,
)
from linhai.machine_control.master_host.process import MasterProcess
from linhai.machine_control.ssh_host.process import RemoteProcess
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class TestProcessCreateResult:
    def test_success(self):
        proc = Mock(spec=Process)
        result = ProcessCreateResult(
            process=proc,
            pid="123",
            returncode=None,
            stdout="out",
            stderr="err",
        )
        assert result.process is proc
        assert result.pid == "123"
        assert result.returncode is None
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.error == ""

    def test_exited(self):
        result = ProcessCreateResult(
            process=None,
            pid="456",
            returncode=0,
            stdout="done",
        )
        assert result.process is None
        assert result.returncode == 0

    def test_error(self):
        result = ProcessCreateResult(
            process=None,
            pid="",
            error="failed",
        )
        assert result.error == "failed"


class TestProcessStdioResult:
    def test_success(self):
        result = ProcessStdioResult(success=True, pid="1", stdout="hello")
        assert result.success is True
        assert result.stdout == "hello"

    def test_failure(self):
        result = ProcessStdioResult(success=False, pid="1", error="not found")
        assert result.success is False
        assert result.error == "not found"


class TestProcessWaitResult:
    def test_success(self):
        result = ProcessWaitResult(success=True, pid="1", returncode=0)
        assert result.success is True
        assert result.returncode == 0

    def test_timeout(self):
        result = ProcessWaitResult(success=False, pid="1", timeout=True)
        assert result.timeout is True


class TestProcessKillResult:
    def test_success(self):
        result = ProcessKillResult(success=True, pid="1")
        assert result.success is True


class TestMasterProcess:
    @pytest.fixture
    def async_proc(self):
        proc = Mock(spec=asyncio.subprocess.Process)
        proc.pid = 12345
        proc.returncode = None
        proc.stdin = Mock()
        proc.stdin.write = Mock()
        proc.stdin.drain = AsyncMock()
        proc.stdout = Mock()
        proc.stdout.read = AsyncMock(return_value=b"output")
        proc.stderr = Mock()
        proc.stderr.read = AsyncMock(return_value=b"")
        proc.wait = AsyncMock(return_value=0)
        proc.terminate = Mock()
        proc.kill = Mock()
        return proc

    @pytest.fixture
    def master_process(self, async_proc):
        on_exit = Mock()
        return MasterProcess(pid="12345", process=async_proc, on_exit=on_exit)

    def test_pid(self, master_process):
        assert master_process.pid == "12345"

    def test_returncode_none(self, master_process):
        assert master_process.returncode is None

    @pytest.mark.asyncio
    async def test_stdio_write_success(self, master_process, async_proc):
        result = await master_process.stdio_write("hello", with_enter=True)
        assert result.success is True
        assert result.pid == "12345"
        async_proc.stdin.write.assert_called()
        async_proc.stdin.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stdio_write_no_stdin(self, master_process, async_proc):
        async_proc.stdin = None
        result = await master_process.stdio_write("hello", with_enter=False)
        assert result.success is False
        assert "stdin" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stdio_read_success(self, master_process, async_proc):
        result = await master_process.stdio_read()
        assert result.success is True
        assert result.stdout == "output"

    @pytest.mark.asyncio
    async def test_wait_success(self, master_process, async_proc):
        result = await master_process.wait(timeout=10)
        assert result.success is True
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_wait_triggers_on_exit(self, master_process, async_proc):
        await master_process.wait(timeout=10)
        master_process._on_exit.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_kill_graceful(self, master_process, async_proc):
        result = await master_process.kill(graceful=True)
        assert result.success is True
        async_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_kill_force(self, master_process, async_proc):
        result = await master_process.kill(graceful=False)
        assert result.success is True
        async_proc.kill.assert_called_once()


class TestRemoteProcess:
    @pytest.fixture
    def remote_process(self):
        call_tool = AsyncMock()
        on_exit = Mock()
        return RemoteProcess(pid="remote-1", call_tool=call_tool, on_exit=on_exit)

    def test_pid(self, remote_process):
        assert remote_process.pid == "remote-1"

    def test_returncode_initial(self, remote_process):
        assert remote_process.returncode is None

    @pytest.mark.asyncio
    async def test_stdio_write(self, remote_process):
        remote_process._call_tool.return_value = ToolResultSuccess(
            content=json.dumps({"success": True}), tool_name="process_stdio_write"
        )
        result = await remote_process.stdio_write("hello", with_enter=True)
        assert result.success is True
        remote_process._call_tool.assert_awaited_once_with(
            "process_stdio_write",
            {"pid": "remote-1", "content": "hello", "with_enter": True},
        )

    @pytest.mark.asyncio
    async def test_stdio_read(self, remote_process):
        remote_process._call_tool.return_value = ToolResultSuccess(
            content=json.dumps({"success": True, "stdout": "data"}),
            tool_name="process_stdio_read",
        )
        result = await remote_process.stdio_read()
        assert result.success is True
        assert result.stdout == "data"

    @pytest.mark.asyncio
    async def test_wait_updates_returncode(self, remote_process):
        remote_process._call_tool.return_value = ToolResultSuccess(
            content=json.dumps({"success": True, "returncode": 42}),
            tool_name="process_wait",
        )
        result = await remote_process.wait(timeout=30)
        assert result.success is True
        assert result.returncode == 42
        assert remote_process.returncode == 42
        remote_process._on_exit.assert_called_once_with("remote-1")

    @pytest.mark.asyncio
    async def test_kill(self, remote_process):
        remote_process._call_tool.return_value = ToolResultSuccess(
            content=json.dumps({"success": True}), tool_name="process_kill"
        )
        result = await remote_process.kill()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_failed_tool_result(self, remote_process):
        remote_process._call_tool.return_value = ToolResultFailed(
            content="connection lost", tool_name="process_stdio_write"
        )
        result = await remote_process.stdio_write("hello", with_enter=False)
        assert result.success is False
        assert result.error == "connection lost"
