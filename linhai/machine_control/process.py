from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Callable, Awaitable


@dataclass
class ProcessCreateResult:
    process: Process | None
    pid: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""
    error: str = ""


@dataclass
class ProcessStdioResult:
    success: bool
    pid: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_note: str | None = None
    error: str = ""


@dataclass
class ProcessWaitResult:
    success: bool
    pid: str = ""
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    timeout: bool = False


@dataclass
class ProcessKillResult:
    success: bool
    pid: str = ""
    error: str = ""


class Process(Protocol):

    @property
    def pid(self) -> str: ...

    @property
    def returncode(self) -> int | None: ...

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessStdioResult: ...

    async def stdio_read(
        self, unescape_ansi: bool = True, timeout: float = 60.0
    ) -> ProcessStdioResult: ...

    async def wait(self, timeout: float) -> ProcessWaitResult: ...

    async def kill(self, graceful: bool = True) -> ProcessKillResult: ...
