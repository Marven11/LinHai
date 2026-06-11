from __future__ import annotations

import asyncio
import unittest

from linhai.machine_control.master_host.process import LocalProcess


def _make_mock_process(
    pid: int = 1234,
    returncode: int | None = None,
    stdout_data: bytes = b"",
    stderr_data: bytes = b"",
) -> asyncio.subprocess.Process:
    class FakeStream:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0

        async def read(self, n: int = -1) -> bytes:
            if self._pos >= len(self._data):
                return b""
            chunk = self._data[self._pos : self._pos + n]
            self._pos += len(chunk)
            return chunk

    class FakeProcess:
        def __init__(self) -> None:
            self.pid = pid
            self._returncode = returncode
            self.stdin = None
            self.stdout = FakeStream(stdout_data) if stdout_data else None
            self.stderr = FakeStream(stderr_data) if stderr_data else None

        @property
        def returncode(self) -> int | None:
            return self._returncode

        async def wait(self) -> int:
            return self._returncode if self._returncode is not None else 0

    return FakeProcess()


class TestLocalProcessBackgroundReader(unittest.IsolatedAsyncioTestCase):
    async def test_background_reader_captures_stdout(self) -> None:
        fake = _make_mock_process(stdout_data=b"hello world")
        lp = LocalProcess(fake)
        await asyncio.sleep(0.3)
        result = await lp.stdio_read(0.1)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, b"hello world")

    async def test_background_reader_captures_stdout_and_stderr(self) -> None:
        fake = _make_mock_process(stdout_data=b"out", stderr_data=b"err", returncode=0)
        lp = LocalProcess(fake)
        await asyncio.sleep(0.3)
        result = await lp.stdio_read(0.1)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, b"out")
        self.assertEqual(result.stderr, b"err")

    async def test_stdio_read_clears_buffer(self) -> None:
        fake = _make_mock_process(stdout_data=b"data")
        lp = LocalProcess(fake)
        await asyncio.sleep(0.3)
        first = await lp.stdio_read(0.1)
        self.assertEqual(first.stdout, b"data")
        second = await lp.stdio_read(0.1)
        self.assertEqual(second.stdout, b"")

    async def test_wait_returns_success_on_already_exited(self) -> None:
        fake = _make_mock_process(returncode=0, stdout_data=b"done")
        lp = LocalProcess(fake)
        result = await lp.wait(timeout=1.0)
        self.assertTrue(result.success)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "done")

    async def test_wait_returns_success_on_exit(self) -> None:
        fake = _make_mock_process(stdout_data=b"output")
        lp = LocalProcess(fake)
        fake._returncode = 42
        result = await lp.wait(timeout=2.0)
        self.assertTrue(result.success)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(result.stdout, "output")

    async def test_drain_buffers(self) -> None:
        fake = _make_mock_process(returncode=0, stdout_data=b"out", stderr_data=b"err")
        lp = LocalProcess(fake)
        await asyncio.sleep(0.3)
        stdout, stderr = await lp.drain_buffers()
        self.assertEqual(stdout, b"out")
        self.assertEqual(stderr, b"err")
        stdout2, stderr2 = await lp.drain_buffers()
        self.assertEqual(stdout2, b"")
        self.assertEqual(stderr2, b"")

    async def test_stdio_read_after_exit_has_note(self) -> None:
        fake = _make_mock_process(returncode=0, stdout_data=b"data")
        lp = LocalProcess(fake)
        await asyncio.sleep(0.3)
        result = await lp.stdio_read(0.1)
        self.assertIsNotNone(result.exit_note)
        self.assertIn("已经退出", result.exit_note)


class TestLocalProcessPid(unittest.TestCase):
    def test_pid_property(self) -> None:
        fake = _make_mock_process(pid=9999)
        lp = LocalProcess(fake)
        self.assertEqual(lp.pid, "9999")

    def test_returncode_property(self) -> None:
        fake = _make_mock_process(returncode=7)
        lp = LocalProcess(fake)
        self.assertEqual(lp.returncode, 7)


class TestLocalProcessWaitTimeout(unittest.IsolatedAsyncioTestCase):
    async def test_wait_timeout_returns_success_with_none_returncode(self) -> None:
        fake = _make_mock_process(stdout_data=b"")
        lp = LocalProcess(fake)
        result = await lp.wait(timeout=0.1)
        self.assertTrue(result.success)
        self.assertIsNone(result.returncode)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


class TestLocalProcessStdioReadThenWait(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_read_partial_then_wait_gets_remaining(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            "echo hello; sleep 0.5; echo world",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        lp = LocalProcess(proc)
        await asyncio.sleep(0.8)
        read_result = await lp.stdio_read(0.1)
        self.assertIn(b"hello", read_result.stdout)
        wait_result = await lp.wait(timeout=5.0)
        self.assertTrue(wait_result.success)
        self.assertEqual(wait_result.returncode, 0)
        combined = read_result.stdout + wait_result.stdout.encode()
        self.assertIn(b"hello", combined)
        self.assertIn(b"world", combined)


class TestLocalProcessE2e(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_read_after_process_exit(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            "ls / && sleep 1 && exit",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        lp = LocalProcess(proc)
        await asyncio.sleep(3)
        result = await lp.stdio_read(0.1)
        self.assertTrue(result.success)
        stdout_text = result.stdout.decode("utf-8", errors="replace")
        self.assertIn("bin", stdout_text)
        self.assertIn("etc", stdout_text)
        self.assertIsNotNone(result.exit_note)

    async def test_wait_timeout_on_long_running_process(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "sleep",
            "30",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        lp = LocalProcess(proc)
        result = await lp.wait(timeout=0.5)
        self.assertTrue(result.success)
        self.assertIsNone(result.returncode)
        await lp.kill()


if __name__ == "__main__":
    unittest.main()
