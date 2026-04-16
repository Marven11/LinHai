from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from linhai.machine_control.process import (
    ProcessKillResult,
    ProcessReadResult,
    ProcessWaitResult,
    ProcessWriteResult,
)


async def _read_stream_chunk(
    stream: asyncio.StreamReader | None, timeout: float, max_size: int
) -> bytes:
    if stream is None:
        return b""
    task = asyncio.ensure_future(stream.read(max_size))
    done, pending = await asyncio.wait({task}, timeout=timeout)
    if pending:
        task.cancel()
        return b""
    return task.result() or b""


async def _wait_process_exit(
    process: asyncio.subprocess.Process, timeout: float
) -> bool:
    task = asyncio.ensure_future(process.wait())
    done, pending = await asyncio.wait({task}, timeout=timeout)
    if pending:
        task.cancel()
        return False
    return True


class LocalProcess:
    def __init__(
        self,
        process: asyncio.subprocess.Process,
        on_exit: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._process = process
        self._on_exit = on_exit
        self._exited = False

    @property
    def pid(self) -> str:
        return str(self._process.pid)

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        pid = self.pid
        if self._process.stdin is None:
            return ProcessWriteResult(
                pid=pid, success=False, error=f"进程 {pid} 没有标准输入"
            )
        if with_enter:
            content = content + "\n"
        self._process.stdin.write(content.encode("utf-8"))
        await self._process.stdin.drain()
        return ProcessWriteResult(pid=pid, success=True, message="写入成功")

    async def stdio_read(self, wait_seconds: float) -> ProcessReadResult:
        pid = self.pid
        stdout_data, stderr_data = await self._read_nonblocking(wait_seconds)
        exit_note = None
        if self._process.returncode is not None:
            exit_note = f"注意：当前程序{pid}已经退出\n"
        return ProcessReadResult(
            pid=pid,
            success=True,
            stdout=stdout_data,
            stderr=stderr_data,
            exit_note=exit_note,
        )

    async def _read_nonblocking(
        self, wait_seconds: float, max_read_size: int = 32768
    ) -> tuple[bytes, bytes]:
        stdout_data = b""
        stderr_data = b""
        start = time.perf_counter()
        while time.perf_counter() - start < wait_seconds:
            remaining = wait_seconds - (time.perf_counter() - start)
            if remaining <= 0:
                break
            interval = min(0.5, remaining)
            if self._process.stdout and len(stdout_data) < max_read_size:
                chunk = await _read_stream_chunk(
                    self._process.stdout,
                    interval,
                    min(4096, max_read_size - len(stdout_data)),
                )
                stdout_data += chunk
            if self._process.stderr and len(stderr_data) < max_read_size:
                chunk = await _read_stream_chunk(
                    self._process.stderr,
                    interval,
                    min(4096, max_read_size - len(stderr_data)),
                )
                stderr_data += chunk
        return stdout_data, stderr_data

    async def wait(self, timeout: float) -> ProcessWaitResult:
        pid = self.pid
        if timeout > 3600:
            return ProcessWaitResult(
                pid=pid, success=False, error="超时时间不能超过3600秒"
            )
        exited = await _wait_process_exit(self._process, timeout)
        if not exited:
            return ProcessWaitResult(
                pid=pid, success=False, error=f"等待进程 {pid} 超时"
            )
        stdout_data, stderr_data = b"", b""
        if self._process.stdout:
            stdout_data = await self._process.stdout.read()
        if self._process.stderr:
            stderr_data = await self._process.stderr.read()
        if self._on_exit and not self._exited:
            self._exited = True
            await self._on_exit(pid)
        return ProcessWaitResult(
            pid=pid,
            success=True,
            returncode=self._process.returncode,
            stdout=stdout_data.decode("utf-8", errors="replace"),
            stderr=stderr_data.decode("utf-8", errors="replace"),
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        pid = self.pid
        if graceful:
            self._process.terminate()
            exited = await _wait_process_exit(self._process, 5.0)
            if not exited:
                self._process.kill()
                await _wait_process_exit(self._process, 5.0)
        else:
            self._process.kill()
            await _wait_process_exit(self._process, 5.0)
        if self._on_exit and not self._exited:
            self._exited = True
            await self._on_exit(pid)
        return ProcessKillResult(pid=pid, success=True, message="进程已终止")
