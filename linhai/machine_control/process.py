from __future__ import annotations

import dataclasses
from typing import Protocol


@dataclasses.dataclass
class ProcessResultBase:
    pid: str
    success: bool
    error: str | None = None


@dataclasses.dataclass
class ProcessCreateResult(ProcessResultBase):
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    message: str = ""


@dataclasses.dataclass
class ProcessWriteResult(ProcessResultBase):
    message: str = ""


@dataclasses.dataclass
class ProcessReadResult(ProcessResultBase):
    stdout: bytes = b""
    stderr: bytes = b""
    exit_note: str | None = None


@dataclasses.dataclass
class ProcessWaitResult(ProcessResultBase):
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


@dataclasses.dataclass
class ProcessKillResult(ProcessResultBase):
    message: str = ""


class Process(Protocol):
    @property
    def pid(self) -> str: ...

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult: ...

    async def stdio_read(self, wait_seconds: float) -> ProcessReadResult: ...

    async def wait(self, timeout: float) -> ProcessWaitResult: ...

    async def kill(self, graceful: bool = True) -> ProcessKillResult: ...
