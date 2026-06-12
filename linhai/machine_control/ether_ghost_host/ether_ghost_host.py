"""EtherGhost机器控制类，用于通过webshell控制远程机器。"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, Union

from linhai.machine_control.http_message import HttpToolResult, build_http_message
from linhai.tool.base import (
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
)
from ..protocol import HostControl
from ..process import Process, ProcessCreateResult


from ether_ghost import session_manager
from ether_ghost.core.base import SessionInterface, session_type_info
from ether_ghost.utils import db


class EtherGhostMachineControl(HostControl):
    """通过EtherGhost webshell控制远程机器。"""

    def __init__(
        self,
        session_type: str,
        connection_args: Dict[str, Any],
        machine_id: str,
    ) -> None:
        self.machine_id = machine_id
        self.session_type = session_type
        self.connection_args = connection_args
        self._uuid = str(uuid.uuid4())

        self.session: Optional[SessionInterface] = None
        self.current_dir: Optional[str] = None

    async def initialize(self) -> None:

        if self.session_type not in session_type_info:
            raise RuntimeError(f"不支持的session类型: {self.session_type}")

        info = session_type_info[self.session_type]
        constructor = info.get("constructor")
        if constructor is None:
            raise RuntimeError(f"session类型 {self.session_type} 没有构造函数")

        self.session = constructor(self.connection_args)
        self.current_dir = await self.session.get_pwd()

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        unsupported = []
        if follow_redirects:
            unsupported.append("follow_redirects")
        if timeout != 60:
            unsupported.append("timeout")
        if auth is not None:
            unsupported.append("auth")
        if cookies is not None:
            unsupported.append("cookies")
        if json_data is not None:
            unsupported.append("json_data")
        if proxy is not None:
            unsupported.append("proxy")
        if verify is not None:
            unsupported.append("verify")

        if unsupported:
            return FailedToolResult(
                content=f"EtherGhost不支持以下参数: {', '.join(unsupported)}"
            )

        response = await self.session.send_http_request(
            url=url,
            method=method,
            params=params,
            data=data,
            headers=headers,
        )

        content_type = response["headers"].get("content-type", "")
        return await build_http_message(
            status_code=response["status_code"],
            headers=response["headers"],
            content=response["body"],
            content_type=content_type.lower() if content_type else "",
        )

    async def change_directory(
        self, directory: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.current_dir is None:
            return FailedToolResult(content="当前目录未知")
        return FailedToolResult(
            content=f"因webshell限制，EtherGhost不支持change_directory，当前路径固定为{self.current_dir}"
        )

    async def create_process(
        self,
        argv: list[str],
        wait_second: Optional[float] = None,
        override_env: Optional[Dict[str, str]] = None,
    ) -> ProcessCreateResult:
        if self.session is None:
            return ProcessCreateResult(pid="", success=False, error="Session未初始化")

        if wait_second is None:
            cmd = " ".join(argv)
            result = await self.session.execute_cmd(cmd)
            return ProcessCreateResult(
                pid="",
                success=True,
                returncode=0,
                stdout=result,
                message=f"命令执行结果:\n{result}\n\n警告: EtherGhost不支持指定wait_seconds",
            )
        return ProcessCreateResult(
            pid="",
            success=False,
            error="EtherGhost不支持wait_second参数，请使用wait_second=None",
        )

    def get_process(self, pid: str) -> Process | None:
        return None

    def list_process_pids(self) -> list[str]:
        return []

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="EtherGhost不支持终端操作")

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="EtherGhost不支持终端操作")

    async def terminal_send_string(
        self,
        terminal_id: str,
        string: str,
        with_enter: bool = True,
        wait_seconds: float = 0.3,
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="EtherGhost不支持终端操作")

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="EtherGhost不支持终端操作")

    async def terminal_close(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="EtherGhost不支持终端操作")

    async def get_terminals(self) -> SuccessfulToolResult | FailedToolResult:
        return SuccessfulToolResult(content="EtherGhost不支持终端操作")

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> Union[SuccessfulToolResult, FailedToolResult, FileContentToolResult]:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        content_bytes = await self.session.get_file_contents(filepath)
        content = content_bytes.decode("utf-8", errors="replace")
        if show_line_numbers:
            lines = content.splitlines(keepends=True)
            if lines:
                numbered_lines = []
                for i, line in enumerate(lines):
                    numbered_lines.append(f"{i+1:4d}: {line}")
                content = "".join(numbered_lines)
        return FileContentToolResult(
            filepath=filepath,
            content=content,
            show_line_numbers=show_line_numbers,
        )

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        if override:
            return FailedToolResult(
                content="禁止override: 非master_host，请妥善处理其他机器上的文件，"
                "考虑手动备份到临时目录，如果你确实需要删除重写，尝试rm"
            )

        content_bytes = content.encode("utf-8")
        success = await self.session.put_file_contents(filepath, content_bytes)
        if success:
            return SuccessfulToolResult(content=f"文件已写入: {filepath}")
        return FailedToolResult(content="写入文件失败")

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        content_bytes = await self.session.get_file_contents(filepath)
        content = content_bytes.decode("utf-8", errors="replace")
        if replace_times is None:
            count = content.count(old)
            if count != 1:
                return FailedToolResult(
                    content=f"旧内容出现次数不为1，实际出现{count}次"
                )
            new_content = content.replace(old, new, 1)
        elif replace_times == -1:
            new_content = content.replace(old, new)
        else:
            new_content = content.replace(old, new, replace_times)

        success = await self.session.put_file_contents(
            filepath, new_content.encode("utf-8")
        )
        if success:
            return SuccessfulToolResult(content="文件内容已替换")
        return FailedToolResult(content="替换文件内容失败")

    async def list_files(self, dirpath: str) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        entries = await self.session.list_dir(dirpath)
        lines = []
        for entry in entries:
            if entry.entry_type == "dir":
                prefix = "d"
            elif entry.entry_type in ("link-dir", "link-file"):
                prefix = "l"
            elif entry.entry_type == "unknown":
                prefix = "?"
            else:
                prefix = "-"
            lines.append(f"{prefix}{entry.permission} {entry.filesize:8d} {entry.name}")
        return SuccessfulToolResult(content="\n".join(lines))

    async def list_files_glob(
        self, pattern: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="list_files_glob仅支持master_host")

    async def get_absolute_path(
        self, path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        result = await self.session.execute_cmd(f"realpath {path}")
        return SuccessfulToolResult(content=result.strip())

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        cmd = f"if command -v sed >/dev/null 2>&1; then sed '{expression}' {filepath}; else echo {self._uuid}; fi"
        result = await self.session.execute_cmd(cmd)
        if self._uuid in result:
            return FailedToolResult(content=f"目标机器上未安装sed (uuid: {self._uuid})")
        return SuccessfulToolResult(content=result)

    async def ping(self) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")
        if await self.session.test_usablility():
            return SuccessfulToolResult(content="pong")
        return FailedToolResult(content="ping failed: session not usable")

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        content_bytes = await self.session.download_file(remote_path)
        Path(local_path).write_bytes(content_bytes)
        return SuccessfulToolResult(content=f"文件已下载: {local_path}")

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.session is None:
            return FailedToolResult(content="Session未初始化")

        success = await self.session.upload_file(remote_path, data)
        if success:
            return SuccessfulToolResult(content=f"文件已上传: {remote_path}")
        else:
            return FailedToolResult(content="上传文件失败")

    async def disconnect(self) -> None:
        self.session = None
