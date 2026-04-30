"""Master host control module for tools that interact with the local machine."""

import asyncio
import fcntl
import os
import pty as pty_module
import time
from pathlib import Path
from typing import Optional

from linhai.machine_control.http_message import HttpMessage
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.agent.messages import FileContentMessage
from linhai.registry import Registry
from linhai.sandbox import ProcessSandboxProtocol
from linhai.machine_control.process import (
    Process,
    ProcessCreateResult,
    ProcessCreateInfo,
)

from .http import http_request
from .terminal import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    configure_terminals,
)
from .file import (
    read_file,
    write_file,
    replace_file_content,
    list_files,
    list_files_glob,
    read_file_with_sed,
)
from .process import LocalProcess, LocalPtyProcess


class MasterHostControl:
    """本地主机控制类，负责提供本地机器工具的实现。

    注意：此类只提供工具方法的实现，不管理工具定义。
    工具定义由MachineControl统一管理。
    """

    def __init__(self, registry: Registry, tmux_terminal: bool = True):
        self._registry = registry
        self._machine_id = "master_host"
        self._cwd = os.getcwd()
        self._processes: dict[str, LocalProcess | LocalPtyProcess] = {}
        configure_terminals(tmux_terminal)

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self._cwd) / p

    def resolve_path(self, path: str) -> Path:
        return self._resolve_path(path)

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[dict] = None,
        json_data: Optional[dict] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpMessage | FailedToolResult:
        """发送HTTP请求并返回响应内容或文件路径"""
        return await http_request(
            method,
            url,
            params,
            headers,
            data,
            follow_redirects,
            timeout,
            auth,
            cookies,
            json_data,
            proxy,
            verify,
        )

    async def _notify_process_created(self, pid: str, argv: list[str]) -> None:
        if "lifecycle" not in self._registry.members:
            return
        from linhai.agent.lifecycle import Lifecycle

        process = self.get_process(pid)
        if process is None:
            return
        lifecycle = self._registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.after_process_create.trigger(
            ProcessCreateInfo(
                process=process,
                argv=argv,
                machine_id=self._machine_id,
            )
        )

    async def create_process(
        self,
        argv: list[str],
        wait_second: Optional[float] = None,
        pty: bool = False,
        env: Optional[dict[str, str]] = None,
    ) -> ProcessCreateResult:
        try:
            sandbox = self._registry.get_member_typechecked(
                "process_sandbox", ProcessSandboxProtocol
            )
            wrapped_argv = sandbox.wrap_argv(argv)
            if pty:
                master_fd, slave_fd = pty_module.openpty()
                subprocess = await asyncio.create_subprocess_exec(
                    *wrapped_argv,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=self._cwd,
                    env=env,
                    start_new_session=True,
                )
                fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
                pid = str(subprocess.pid)
                lp = LocalPtyProcess(
                    subprocess, master_fd, slave_fd, on_exit=self._handle_process_exit
                )
                self._processes[pid] = lp
                await self._notify_process_created(pid, argv)
                if wait_second is None:
                    wait_second = 1.0
                start = time.perf_counter()
                while time.perf_counter() - start < wait_second:
                    await asyncio.sleep(0.1)
                    if subprocess.returncode is not None:
                        break
                if subprocess.returncode is not None:
                    stdout_bytes, _ = await lp.drain_buffers()
                    return ProcessCreateResult(
                        pid=pid,
                        success=True,
                        returncode=subprocess.returncode,
                        stdout=stdout_bytes.decode("utf-8", errors="replace"),
                        stderr="",
                    )
                return ProcessCreateResult(
                    pid=pid,
                    success=True,
                    returncode=None,
                    message=f"等待失败，程序在{wait_second}秒后在运行(pty模式)。建议使用process_*系列工具进行读写stdio或者进一步等待程序",
                )
            subprocess = await asyncio.create_subprocess_exec(
                *wrapped_argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=env,
                start_new_session=True,
            )
            pid = str(subprocess.pid)
            lp = LocalProcess(subprocess, on_exit=self._handle_process_exit)
            self._processes[pid] = lp
            await self._notify_process_created(pid, argv)

            if wait_second is None:
                wait_second = 1.0

            start = time.perf_counter()
            while time.perf_counter() - start < wait_second:
                await asyncio.sleep(0.1)
                if subprocess.returncode is not None:
                    break

            if subprocess.returncode is not None:
                stdout_bytes, stderr_bytes = await lp.drain_buffers()
                return ProcessCreateResult(
                    pid=pid,
                    success=True,
                    returncode=subprocess.returncode,
                    stdout=stdout_bytes.decode("utf-8", errors="replace"),
                    stderr=stderr_bytes.decode("utf-8", errors="replace"),
                )

            return ProcessCreateResult(
                pid=pid,
                success=True,
                returncode=None,
                message=f"等待失败，程序在{wait_second}秒后在运行。建议使用process_*系列工具进行读写stdio或者进一步等待程序",
            )
        except Exception as e:
            return ProcessCreateResult(pid="", success=False, error=str(e))

    def get_process(self, pid: str) -> Process | None:
        return self._processes.get(pid)

    def list_process_pids(self) -> list[str]:
        return list(self._processes.keys())

    async def _handle_process_exit(self, pid: str) -> None:
        pass

    async def change_directory(
        self, directory: str
    ) -> SuccessfulToolResult | FailedToolResult:
        target = self._resolve_path(directory)
        if not target.exists():
            return FailedToolResult(content=f"目录不存在: {directory}")
        if not target.is_dir():
            return FailedToolResult(content=f"路径不是目录: {directory}")
        old_cwd = self._cwd
        self._cwd = str(target)
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        sandbox.update_pwd(self._cwd)
        return SuccessfulToolResult(content=f"从目录{old_cwd}切换到了{self._cwd}")

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult:
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        shell_argv = sandbox.wrap_argv(["/usr/bin/env", "bash"])
        result = await terminal_create(columns, lines, shell_argv, cwd=self._cwd)
        if result.startswith("创建终端失败"):
            return FailedToolResult(content=result)
        return SuccessfulToolResult(content=result)

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult:
        result = await terminal_send_keys(terminal_id, keys)
        if result.startswith("错误") or result.startswith("未知按键"):
            return FailedToolResult(content=result)
        return SuccessfulToolResult(content=result)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> SuccessfulToolResult | FailedToolResult:
        result = await terminal_send_string(
            terminal_id, string, with_enter, wait_seconds
        )
        if result.startswith("错误"):
            return FailedToolResult(content=result)
        return SuccessfulToolResult(content=result)

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        result = await terminal_read_screen(terminal_id)
        if result.startswith("错误"):
            return FailedToolResult(content=result)
        return SuccessfulToolResult(content=result)

    async def terminal_close(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        result = await terminal_close(terminal_id)
        if result.startswith("错误"):
            return FailedToolResult(content=result)
        return SuccessfulToolResult(content=result)

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> FileContentMessage | FailedToolResult:
        resolved = self._resolve_path(filepath)
        return await asyncio.to_thread(read_file, str(resolved), show_line_numbers)

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        resolved = self._resolve_path(filepath)
        return await asyncio.to_thread(write_file, str(resolved), content, override)

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult:
        resolved = self._resolve_path(filepath)
        return await asyncio.to_thread(
            replace_file_content, str(resolved), old, new, replace_times
        )

    async def list_files(
        self, dirpath: str, glob: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        if glob:
            return await asyncio.to_thread(list_files_glob, self._cwd, dirpath)
        resolved = self._resolve_path(dirpath)
        return await asyncio.to_thread(list_files, str(resolved))

    async def get_absolute_path(
        self, path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        resolved = self._resolve_path(path)
        return SuccessfulToolResult(content=f"绝对路径: {resolved.as_posix()}")

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult:
        resolved = self._resolve_path(filepath)
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        return await asyncio.to_thread(
            read_file_with_sed, expression, str(resolved), sandbox.wrap_argv
        )

    async def get_terminals(self) -> SuccessfulToolResult | FailedToolResult:
        """获取所有终端列表"""
        from .terminal import terminals

        if not terminals:
            return SuccessfulToolResult(
                content="<<terminals>>没有活动的终端<<terminals>>"
            )
        lines = []
        for term_id, terminal in terminals.items():
            try:
                screen = terminal.get_screen()
                lines.append(
                    f"<<terminal_id>>{term_id}<<terminal_id>><<machine>>master_host<<machine>><<screen>>{screen}<<screen>>"
                )
            except Exception:
                lines.append(
                    f"<<terminal_id>>{term_id}<<terminal_id>><<machine>>master_host<<machine>><<screen>>无法获取屏幕内容<<screen>>"
                )
        return SuccessfulToolResult(content="\n".join(lines))

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        import pathlib

        resolved = self._resolve_path(remote_path)
        if resolved.exists():
            return FailedToolResult(content=f"文件已存在: {resolved}")
        try:
            pathlib.Path(resolved).write_bytes(data)
            return SuccessfulToolResult(content=f"文件已上传: {resolved}")
        except Exception as e:
            return FailedToolResult(content=f"上传文件失败: {e}")

    async def ping(self) -> SuccessfulToolResult | FailedToolResult:
        return SuccessfulToolResult(content="pong")

    async def disconnect(self) -> None:
        raise RuntimeError("不能断开master_host")

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        import pathlib

        resolved_remote = self._resolve_path(remote_path)
        if not resolved_remote.exists():
            return FailedToolResult(content=f"文件不存在: {resolved_remote}")
        try:
            data = pathlib.Path(resolved_remote).read_bytes()
            pathlib.Path(local_path).write_bytes(data)
            return SuccessfulToolResult(content=f"文件已下载: {local_path}")
        except Exception as e:
            return FailedToolResult(content=f"下载文件失败: {e}")
