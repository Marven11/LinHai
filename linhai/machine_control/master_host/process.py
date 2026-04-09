from __future__ import annotations

import asyncio
import re
from typing import Callable

from linhai.machine_control.process import (
    Process,
    ProcessStdioResult,
    ProcessWaitResult,
    ProcessKillResult,
)


class MasterProcess:
    def __init__(
        self,
        pid: str,
        process: asyncio.subprocess.Process,
        on_exit: Callable[[str], None],
    ):
        self._pid = pid
        self._process = process
        self._on_exit = on_exit
        self._exited = False

    @property
    def pid(self) -> str:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    def _check_exit(self) -> None:
        if not self._exited and self._process.returncode is not None:
            self._exited = True
            self._on_exit(self._pid)

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessStdioResult:
        if self._process.stdin is None:
            return ProcessStdioResult(
                success=False,
                pid=self._pid,
                error="Process stdin is not available",
            )
        data = content.encode("utf-8")
        self._process.stdin.write(data)
        if with_enter:
            self._process.stdin.write(b"\n")
        await self._process.stdin.drain()
        return ProcessStdioResult(
            success=True,
            pid=self._pid,
        )

    def _read_process_stdio(
        self,
        stdout_data: bytes,
        stderr_data: bytes,
        unescape_ansi: bool,
    ) -> tuple[str, str, str | None]:
        def decode(data: bytes) -> str:
            if not data:
                return ""
            text = data.decode("utf-8", errors="replace")
            if unescape_ansi:
                text = self._unescape_ansi(text)
            return text

        stdout_text = decode(stdout_data)
        stderr_text = decode(stderr_data)
        exit_note = None

        if self._process.returncode is not None:
            exit_note = f"Process exited with code {self._process.returncode}"

        return stdout_text, stderr_text, exit_note

    @staticmethod
    def _unescape_ansi(text: str) -> str:
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    async def _read_stream_with_timeout(
        self, stream: asyncio.StreamReader | None, timeout: float
    ) -> bytes:
        if stream is None:
            return b""
        read_task = asyncio.ensure_future(stream.read())
        done, pending = await asyncio.wait({read_task}, timeout=timeout)
        if read_task in pending:
            read_task.cancel()
            return b""
        return read_task.result()

    async def stdio_read(
        self,
        unescape_ansi: bool = True,
        timeout: float = 60.0,
    ) -> ProcessStdioResult:
        stdout_data = await self._read_stream_with_timeout(
            self._process.stdout, timeout
        )
        stderr_data = await self._read_stream_with_timeout(
            self._process.stderr, timeout
        )

        stdout, stderr, exit_note = self._read_process_stdio(
            stdout_data,
            stderr_data,
            unescape_ansi,
        )

        self._check_exit()

        return ProcessStdioResult(
            success=True,
            pid=self._pid,
            stdout=stdout,
            stderr=stderr,
            exit_note=exit_note,
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        wait_task = asyncio.ensure_future(self._process.wait())
        done, pending = await asyncio.wait({wait_task}, timeout=timeout)
        if wait_task in pending:
            wait_task.cancel()
            return ProcessWaitResult(
                success=False,
                pid=self._pid,
                timeout=True,
                error=f"Timeout waiting for process {self._pid}",
            )

        returncode = wait_task.result()
        self._exited = True
        self._on_exit(self._pid)

        stdout_data = await self._read_stream_with_timeout(self._process.stdout, 5.0)
        stderr_data = await self._read_stream_with_timeout(self._process.stderr, 5.0)

        stdout, stderr, _ = self._read_process_stdio(
            stdout_data,
            stderr_data,
            unescape_ansi=True,
        )

        return ProcessWaitResult(
            success=True,
            pid=self._pid,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        if graceful:
            self._process.terminate()
            wait_task = asyncio.ensure_future(self._process.wait())
            done, pending = await asyncio.wait({wait_task}, timeout=5.0)
            if wait_task in pending:
                wait_task.cancel()
                self._process.kill()
                await self._process.wait()
        else:
            self._process.kill()
            await self._process.wait()

        self._exited = True
        self._on_exit(self._pid)

        return ProcessKillResult(
            success=True,
            pid=self._pid,
        )
