from __future__ import annotations

import json
from typing import TYPE_CHECKING

from linhai.machine_control.process import (
    ProcessIOError,
    ProcessKillResult,
    ProcessReadResult,
    ProcessWaitResult,
    ProcessWriteResult,
)
from linhai.tool.base import FailedToolResult, SuccessfulToolResult

if TYPE_CHECKING:
    from .posix_shell_control import PosixShellControl


class RemoteProcess:
    def __init__(self, pid: str, shell_control: "PosixShellControl") -> None:
        self._pid = pid
        self._shell_control = shell_control

    @property
    def pid(self) -> str:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return None

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult | ProcessIOError:
        result = await self._shell_control.call_tool(
            "process_stdio_write",
            {"pid": self._pid, "content": content, "with_enter": with_enter},
        )
        if isinstance(result, FailedToolResult):
            return ProcessIOError(error=result.content)
        return ProcessWriteResult(
            pid=self._pid,
            success=True,
            message=result.content,
        )

    async def stdio_read(
        self, wait_seconds: float
    ) -> ProcessReadResult | ProcessIOError:
        result = await self._shell_control.call_tool(
            "process_stdio_read",
            {
                "pid": self._pid,
                "timeout": wait_seconds,
            },
        )
        if isinstance(result, FailedToolResult):
            return ProcessIOError(error=result.content)
        data = json.loads(result.content)
        return ProcessReadResult(
            pid=self._pid,
            success=data.get("success", True),
            stdout=data.get("stdout", "").encode("utf-8"),
            stderr=data.get("stderr", "").encode("utf-8"),
            exit_note=data.get("exit_note"),
            error=data.get("error"),
        )

    async def wait(self, timeout: float) -> ProcessWaitResult | ProcessIOError:
        result = await self._shell_control.call_tool(
            "process_wait", {"pid": self._pid, "timeout": timeout}
        )
        if isinstance(result, FailedToolResult):
            return ProcessIOError(error=result.content)
        data = json.loads(result.content)
        if data.get("timeout"):
            return ProcessWaitResult(pid=self._pid, success=False, error="等待超时")
        return ProcessWaitResult(
            pid=self._pid,
            success=True,
            returncode=data.get("returncode"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult | ProcessIOError:
        result = await self._shell_control.call_tool(
            "process_kill", {"pid": self._pid, "graceful": graceful}
        )
        if isinstance(result, FailedToolResult):
            return ProcessIOError(error=result.content)
        return ProcessKillResult(pid=self._pid, success=True, message="进程已终止")
