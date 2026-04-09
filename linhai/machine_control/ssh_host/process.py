from __future__ import annotations

import json
from typing import Callable, Awaitable, Any

from linhai.machine_control.process import (
    Process,
    ProcessStdioResult,
    ProcessWaitResult,
    ProcessKillResult,
)
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class RemoteProcess:
    def __init__(
        self,
        pid: str,
        call_tool: Callable[
            [str, dict[str, Any]], Awaitable[ToolResultSuccess | ToolResultFailed]
        ],
        on_exit: Callable[[str], None],
    ):
        self._pid = pid
        self._call_tool = call_tool
        self._on_exit = on_exit
        self._returncode: int | None = None

    @property
    def pid(self) -> str:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def _parse_json_result(
        self, result: ToolResultSuccess | ToolResultFailed
    ) -> dict[str, Any]:
        if isinstance(result, ToolResultSuccess):
            return json.loads(result.content)
        return {"success": False, "error": result.content}

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessStdioResult:
        result = await self._call_tool(
            "process_stdio_write",
            {
                "pid": self._pid,
                "content": content,
                "with_enter": with_enter,
            },
        )
        data = self._parse_json_result(result)
        return ProcessStdioResult(
            success=data.get("success", True),
            pid=self._pid,
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_note=data.get("exit_note"),
            error=data.get("error", ""),
        )

    async def stdio_read(
        self,
        unescape_ansi: bool = True,
        timeout: float = 60.0,
    ) -> ProcessStdioResult:
        result = await self._call_tool(
            "process_stdio_read",
            {
                "pid": self._pid,
                "unescape_ansi": unescape_ansi,
                "timeout": timeout,
            },
        )
        data = self._parse_json_result(result)
        return ProcessStdioResult(
            success=data.get("success", True),
            pid=self._pid,
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_note=data.get("exit_note"),
            error=data.get("error", ""),
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        result = await self._call_tool(
            "process_wait",
            {
                "pid": self._pid,
                "timeout": timeout,
            },
        )
        data = self._parse_json_result(result)
        returncode = data.get("returncode")
        if returncode is not None:
            self._returncode = returncode
            self._on_exit(self._pid)
        return ProcessWaitResult(
            success=data.get("success", True),
            pid=self._pid,
            returncode=returncode,
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            error=data.get("error", ""),
            timeout=data.get("timeout", False),
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        result = await self._call_tool(
            "process_kill",
            {
                "pid": self._pid,
                "graceful": graceful,
            },
        )
        data = self._parse_json_result(result)
        if data.get("success", False):
            self._returncode = data.get("returncode", -1)
            self._on_exit(self._pid)
        return ProcessKillResult(
            success=data.get("success", True),
            pid=self._pid,
            error=data.get("error", ""),
        )
