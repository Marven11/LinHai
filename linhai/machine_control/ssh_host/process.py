from __future__ import annotations

import json
import re

from linhai.machine_control.process import (
    ProcessKillResult,
    ProcessReadResult,
    ProcessWaitResult,
    ProcessWriteResult,
)
from linhai.tool.base import ToolResultSuccess


class RemoteProcess:
    def __init__(self, pid: str, ssh_control) -> None:
        self._pid = pid
        self._ssh_control = ssh_control

    @property
    def pid(self) -> str:
        return self._pid

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        result = await self._ssh_control.call_tool(
            "process_stdio_write",
            {"pid": self._pid, "content": content, "with_enter": with_enter},
        )
        if isinstance(result, ToolResultSuccess):
            data = json.loads(result.content)
            return ProcessWriteResult(
                pid=self._pid,
                success=data.get("success", True),
                message=data.get("message", ""),
                error=data.get("error"),
            )
        return ProcessWriteResult(
            pid=self._pid, success=False, error=str(result.content)
        )

    async def stdio_read(
        self, wait_seconds: float, unescape_ansi: bool = True
    ) -> ProcessReadResult:
        result = await self._ssh_control.call_tool(
            "process_stdio_read",
            {
                "pid": self._pid,
                "unescape_ansi": unescape_ansi,
                "timeout": wait_seconds,
            },
        )
        if isinstance(result, ToolResultSuccess):
            data = json.loads(result.content)
            return ProcessReadResult(
                pid=self._pid,
                success=data.get("success", True),
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                exit_note=data.get("exit_note"),
                error=data.get("error"),
            )
        return ProcessReadResult(
            pid=self._pid, success=False, error=str(result.content)
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        result = await self._ssh_control.call_tool(
            "process_wait", {"pid": self._pid, "timeout": timeout}
        )
        if isinstance(result, ToolResultSuccess):
            returncode = _extract_tag(result.content, "returncode")
            stdout = _extract_tag(result.content, "stdout")
            stderr = _extract_tag(result.content, "stderr")
            return ProcessWaitResult(
                pid=self._pid,
                success=True,
                returncode=int(returncode) if returncode is not None else None,
                stdout=stdout or "",
                stderr=stderr or "",
            )
        return ProcessWaitResult(
            pid=self._pid, success=False, error=str(result.content)
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        result = await self._ssh_control.call_tool(
            "process_kill", {"pid": self._pid, "graceful": graceful}
        )
        if isinstance(result, ToolResultSuccess):
            return ProcessKillResult(pid=self._pid, success=True, message="进程已终止")
        return ProcessKillResult(
            pid=self._pid, success=False, error=str(result.content)
        )


def _extract_tag(content: str, tag: str) -> str | None:
    pattern = f"<<{tag}>>(.*?)<<{tag}>>"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else None
