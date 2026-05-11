"""测试辅助工具模块，包含仅用于测试的类。"""

import asyncio
from typing import Optional

from linhai.machine_control.process import (
    ProcessKillResult,
    ProcessReadResult,
    ProcessWriteResult,
    ProcessWaitResult,
)


class _AsyncioProcessAdapter:
    """仅用于测试的异步进程适配器。"""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    @property
    def pid(self) -> str:
        return str(self._process.pid)

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        if self._process.stdin is None:
            return ProcessWriteResult(pid=self.pid, success=False, error="stdin不可用")
        if with_enter:
            content += "\n"
        self._process.stdin.write(content.encode())
        await self._process.stdin.drain()
        return ProcessWriteResult(pid=self.pid, success=True, message="写入成功")

    async def stdio_read(self, wait_seconds: float) -> ProcessReadResult:
        if self._process.stdout is None:
            return ProcessReadResult(pid=self.pid, success=True, stdout=b"", stderr=b"")

        chunks: list[bytes] = []
        loop = asyncio.get_event_loop()
        start = loop.time()
        while loop.time() - start < wait_seconds:
            remaining = wait_seconds - (loop.time() - start)
            if remaining <= 0:
                break
            read_task = asyncio.ensure_future(self._process.stdout.read(4096))
            done, _ = await asyncio.wait({read_task}, timeout=min(0.5, remaining))
            if not done:
                read_task.cancel()
                if chunks:
                    break
                continue
            data = read_task.result()
            if data:
                chunks.append(data)
            else:
                break

        raw = b"".join(chunks)
        exit_note = None
        if self._process.returncode is not None:
            exit_note = f"注意：当前程序{self.pid}已经退出\n"
        return ProcessReadResult(
            pid=self.pid, success=True, stdout=raw, stderr=b"", exit_note=exit_note
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        wait_task = asyncio.ensure_future(self._process.wait())
        done, _ = await asyncio.wait({wait_task}, timeout=timeout)
        if not done:
            wait_task.cancel()
            return ProcessWaitResult(pid=self.pid, success=False, error="等待超时")
        returncode = wait_task.result()
        return ProcessWaitResult(
            pid=self.pid, success=True, returncode=returncode, stdout="", stderr=""
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        if graceful:
            self._process.terminate()
            wait_task = asyncio.ensure_future(self._process.wait())
            done, _ = await asyncio.wait({wait_task}, timeout=5.0)
            if not done:
                wait_task.cancel()
                self._process.kill()
                await self._process.wait()
        else:
            self._process.kill()
            await self._process.wait()
        return ProcessKillResult(pid=self.pid, success=True, message="进程已终止")
