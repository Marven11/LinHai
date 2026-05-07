from __future__ import annotations

import dataclasses
import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    pass


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


@dataclasses.dataclass
class ProcessIOError:
    error: str


class Process(Protocol):
    @property
    def pid(self) -> str: ...

    @property
    def returncode(self) -> int | None: ...

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult | ProcessIOError: ...

    async def stdio_read(
        self, wait_seconds: float
    ) -> ProcessReadResult | ProcessIOError: ...

    async def wait(self, timeout: float) -> ProcessWaitResult | ProcessIOError: ...

    async def kill(
        self, graceful: bool = True
    ) -> ProcessKillResult | ProcessIOError: ...


@dataclasses.dataclass
class ProcessCreateInfo:
    process: Process
    argv: list[str]
    machine_id: str
    created_at: float = 0.0
    initial_returncode: int | None = None

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
