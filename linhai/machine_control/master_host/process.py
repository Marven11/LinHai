from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from linhai.machine_control.process import (
    ProcessIOError,
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
        self._stdout_buffer = b""
        self._stderr_buffer = b""
        self._reader_task: asyncio.Task[None] | None = None
        self._start_reader()

    def _start_reader(self) -> None:
        if self._process.stdout is not None or self._process.stderr is not None:
            self._reader_task = asyncio.ensure_future(self._background_reader())

    async def _background_reader(self) -> None:
        while True:
            stdout_chunk, stderr_chunk = await asyncio.gather(
                _read_stream_chunk(self._process.stdout, 0.5, 65536),
                _read_stream_chunk(self._process.stderr, 0.5, 65536),
            )
            has_data = False
            if stdout_chunk:
                self._stdout_buffer += stdout_chunk
                has_data = True
            if stderr_chunk:
                self._stderr_buffer += stderr_chunk
                has_data = True
            if self._process.returncode is not None and not has_data:
                stdout_final, stderr_final = await asyncio.gather(
                    _read_stream_chunk(self._process.stdout, 0.1, 65536),
                    _read_stream_chunk(self._process.stderr, 0.1, 65536),
                )
                if stdout_final:
                    self._stdout_buffer += stdout_final
                if stderr_final:
                    self._stderr_buffer += stderr_final
                break
            await asyncio.sleep(0.1)

    @property
    def pid(self) -> str:
        return str(self._process.pid)

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def drain_buffers(self) -> tuple[bytes, bytes]:
        if self._reader_task and not self._reader_task.done():
            await asyncio.wait({self._reader_task}, timeout=0.5)
        stdout = self._stdout_buffer
        stderr = self._stderr_buffer
        self._stdout_buffer = b""
        self._stderr_buffer = b""
        return stdout, stderr

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult | ProcessIOError:
        pid = self.pid
        if self._process.stdin is None:
            return ProcessWriteResult(
                pid=pid, success=False, error=f"进程 {pid} 没有标准输入"
            )
        if self._process.stdin.is_closing():
            return ProcessIOError(error=f"进程 {pid} 标准输入已关闭")
        if with_enter:
            content = content + "\n"
        self._process.stdin.write(content.encode("utf-8"))
        await self._process.stdin.drain()
        return ProcessWriteResult(pid=pid, success=True, message="写入成功")

    async def stdio_read(
        self, wait_seconds: float
    ) -> ProcessReadResult | ProcessIOError:
        pid = self.pid
        await asyncio.sleep(wait_seconds)
        stdout_data = self._stdout_buffer
        stderr_data = self._stderr_buffer
        self._stdout_buffer = b""
        self._stderr_buffer = b""
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

    async def wait(self, timeout: float) -> ProcessWaitResult | ProcessIOError:
        pid = self.pid
        if timeout > 3600:
            return ProcessWaitResult(
                pid=pid, success=False, error="超时时间不能超过3600秒"
            )
        if self._process.returncode is not None:
            if self._reader_task and not self._reader_task.done():
                await asyncio.wait({self._reader_task}, timeout=2.0)
            stdout_data = self._stdout_buffer.decode("utf-8", errors="replace")
            stderr_data = self._stderr_buffer.decode("utf-8", errors="replace")
            self._stdout_buffer = b""
            self._stderr_buffer = b""
            if self._on_exit and not self._exited:
                self._exited = True
                await self._on_exit(pid)
            return ProcessWaitResult(
                pid=pid,
                success=True,
                returncode=self._process.returncode,
                stdout=stdout_data,
                stderr=stderr_data,
            )
        exited = await _wait_process_exit(self._process, timeout)
        if not exited:
            return ProcessWaitResult(
                pid=pid,
                success=True,
                returncode=None,
                stdout="",
                stderr="",
            )
        if self._reader_task and not self._reader_task.done():
            await asyncio.wait({self._reader_task}, timeout=2.0)
        stdout_data = self._stdout_buffer.decode("utf-8", errors="replace")
        stderr_data = self._stderr_buffer.decode("utf-8", errors="replace")
        self._stdout_buffer = b""
        self._stderr_buffer = b""
        if self._on_exit and not self._exited:
            self._exited = True
            await self._on_exit(pid)
        return ProcessWaitResult(
            pid=pid,
            success=True,
            returncode=self._process.returncode,
            stdout=stdout_data,
            stderr=stderr_data,
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult | ProcessIOError:
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
        if self._process.stdin is not None and not self._process.stdin.is_closing():
            self._process.stdin.close()
        if self._reader_task and not self._reader_task.done():
            await asyncio.wait({self._reader_task}, timeout=2.0)
        if self._on_exit and not self._exited:
            self._exited = True
            await self._on_exit(pid)
        return ProcessKillResult(pid=pid, success=True, message="进程已终止")
