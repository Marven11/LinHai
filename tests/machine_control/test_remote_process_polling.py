from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from linhai.machine_control.posix_shell.process import RemoteProcess
from linhai.machine_control.process import (
    ProcessIOError,
    ProcessReadResult,
    ProcessWaitResult,
)
from linhai.tool.base import FailedToolResult, SuccessfulToolResult


def _make_shell_control() -> MagicMock:
    sc = MagicMock()
    sc.call_tool = AsyncMock()
    return sc


class TestRemoteProcessWaitPolling(unittest.IsolatedAsyncioTestCase):
    async def test_wait_short_timeout_single_call(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = SuccessfulToolResult(
            content=json.dumps(
                {"pid": "1", "returncode": 0, "stdout": "done", "stderr": ""}
            )
        )
        rp = RemoteProcess("1", sc)
        result = await rp.wait(3.0)
        self.assertTrue(result.success)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(sc.call_tool.call_count, 1)
        sent_timeout = sc.call_tool.call_args[0][1]["timeout"]
        self.assertEqual(sent_timeout, 3.0)

    async def test_wait_long_timeout_polls_multiple_times_until_exit(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.side_effect = [
            SuccessfulToolResult(content=json.dumps({"pid": "1", "timeout": True})),
            SuccessfulToolResult(content=json.dumps({"pid": "1", "timeout": True})),
            SuccessfulToolResult(
                content=json.dumps(
                    {"pid": "1", "returncode": 42, "stdout": "ok", "stderr": ""}
                )
            ),
        ]
        rp = RemoteProcess("1", sc)
        result = await rp.wait(12.0)
        self.assertTrue(result.success)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(sc.call_tool.call_count, 3)

    async def test_wait_long_timeout_expires_returns_none(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = SuccessfulToolResult(
            content=json.dumps({"pid": "1", "timeout": True})
        )
        rp = RemoteProcess("1", sc)
        result = await rp.wait(12.0)
        self.assertTrue(result.success)
        self.assertIsNone(result.returncode)
        expected_calls = 3
        self.assertEqual(sc.call_tool.call_count, expected_calls)

    async def test_wait_io_error(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = FailedToolResult(content="连接断开")
        rp = RemoteProcess("1", sc)
        result = await rp.wait(3.0)
        self.assertIsInstance(result, ProcessIOError)
        self.assertIn("连接断开", result.error)

    async def test_wait_each_poll_uses_max_5_seconds(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = SuccessfulToolResult(
            content=json.dumps({"pid": "1", "timeout": True})
        )
        rp = RemoteProcess("1", sc)
        await rp.wait(13.0)
        timeouts = [call.args[1]["timeout"] for call in sc.call_tool.call_args_list]
        for t in timeouts:
            self.assertLessEqual(t, 5.0)


class TestRemoteProcessStdioReadPolling(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_read_short_timeout_single_call(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = SuccessfulToolResult(
            content=json.dumps({"pid": "1", "stdout": "hello", "stderr": ""})
        )
        rp = RemoteProcess("1", sc)
        result = await rp.stdio_read(3.0)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, b"hello")
        self.assertEqual(sc.call_tool.call_count, 1)

    async def test_stdio_read_long_timeout_accumulates_output(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.side_effect = [
            SuccessfulToolResult(
                content=json.dumps({"pid": "1", "stdout": "chunk1", "stderr": "err1"})
            ),
            SuccessfulToolResult(
                content=json.dumps({"pid": "1", "stdout": "chunk2", "stderr": "err2"})
            ),
            SuccessfulToolResult(
                content=json.dumps({"pid": "1", "stdout": "chunk3", "stderr": "err3"})
            ),
        ]
        rp = RemoteProcess("1", sc)
        result = await rp.stdio_read(12.0)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, b"chunk1chunk2chunk3")
        self.assertEqual(result.stderr, b"err1err2err3")
        self.assertEqual(sc.call_tool.call_count, 3)

    async def test_stdio_read_long_timeout_captures_exit_note(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.side_effect = [
            SuccessfulToolResult(
                content=json.dumps({"pid": "1", "stdout": "", "stderr": ""})
            ),
            SuccessfulToolResult(
                content=json.dumps(
                    {"pid": "1", "stdout": "done", "stderr": "", "exit_note": "已退出"}
                )
            ),
        ]
        rp = RemoteProcess("1", sc)
        result = await rp.stdio_read(8.0)
        self.assertIsNotNone(result.exit_note)
        self.assertIn("已退出", result.exit_note)

    async def test_stdio_read_io_error(self) -> None:
        sc = _make_shell_control()
        sc.call_tool.return_value = FailedToolResult(content="IO失败")
        rp = RemoteProcess("1", sc)
        result = await rp.stdio_read(3.0)
        self.assertIsInstance(result, ProcessIOError)
        self.assertIn("IO失败", result.error)


if __name__ == "__main__":
    unittest.main()
