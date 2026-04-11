"""Master host control module for tools that interact with the local machine."""

import asyncio
import time
from typing import Optional, Union
from linhai.machine_control.http_message import HttpMessage
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.llm import Message
from linhai.agent.messages import FileContentMessage

from .http import http_request
from .command import change_directory
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
    get_absolute_path,
    read_file_with_sed,
    modify_file_with_sed,
)


from linhai.registry import Registry
from .process import LocalProcess
from linhai.sandbox import ProcessSandboxProtocol
from linhai.machine_control.process import Process, ProcessCreateResult


class MasterHostControl:
    """本地主机控制类，负责提供本地机器工具的实现。

    注意：此类只提供工具方法的实现，不管理工具定义。
    工具定义由MachineControl统一管理。
    """

    def __init__(self, registry: Registry, tmux_terminal: bool = True):
        self._registry = registry
        self._processes: dict[str, LocalProcess] = {}
        configure_terminals(tmux_terminal)

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
    ) -> HttpMessage | ToolResultFailed:
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

    async def create_process(
        self, argv: list[str], wait_second: Optional[float] = None
    ) -> ProcessCreateResult:
        try:
            sandbox = self._registry.get_member_typechecked(
                "process_sandbox", ProcessSandboxProtocol
            )
            wrapped_argv = sandbox.wrap_argv(argv)
            subprocess = await asyncio.create_subprocess_exec(
                *wrapped_argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            pid = str(subprocess.pid)
            lp = LocalProcess(subprocess, on_exit=self._handle_process_exit)
            self._processes[pid] = lp

            if wait_second is None:
                wait_second = 1.0

            start = time.perf_counter()
            while time.perf_counter() - start < wait_second:
                await asyncio.sleep(0.1)
                if subprocess.returncode is not None:
                    break

            if subprocess.returncode is not None:
                del self._processes[pid]
                read_result = await lp.stdio_read(wait_seconds=2.0)
                return ProcessCreateResult(
                    pid=pid,
                    success=True,
                    returncode=subprocess.returncode,
                    stdout=read_result.stdout,
                    stderr=read_result.stderr,
                )

            read_result = await lp.stdio_read(wait_seconds=2.0)
            message = f"等待失败，程序在{wait_second}秒后在运行。"
            if read_result.stdout or read_result.stderr:
                message += f" 至今为止该进程已输出到stdout/stderr的内容：\nstdout:\n{read_result.stdout}\nstderr:\n{read_result.stderr}"
            else:
                message += " 建议使用process_*系列工具进行读写stdio或者进一步等待程序"
            return ProcessCreateResult(
                pid=pid,
                success=True,
                returncode=None,
                stdout=read_result.stdout,
                stderr=read_result.stderr,
                message=message,
            )
        except Exception as e:
            return ProcessCreateResult(pid="", success=False, error=str(e))

    def get_process(self, pid: str) -> Process | None:
        return self._processes.get(pid)

    async def _handle_process_exit(self, pid: str) -> None:
        self._processes.pop(pid, None)

    async def change_directory(
        self, directory: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """改变当前工作目录"""
        return change_directory(directory)

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed:
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        bash_argv = sandbox.wrap_argv(["/usr/bin/env", "bash"])
        result = await terminal_create(columns, lines, bash_argv)
        if result.startswith("创建终端失败"):
            return ToolResultFailed(content=result)
        return ToolResultSuccess(content=result)

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed:
        result = await terminal_send_keys(terminal_id, keys)
        if result.startswith("错误") or result.startswith("未知按键"):
            return ToolResultFailed(content=result)
        return ToolResultSuccess(content=result)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> ToolResultSuccess | ToolResultFailed:
        result = await terminal_send_string(
            terminal_id, string, with_enter, wait_seconds
        )
        if result.startswith("错误"):
            return ToolResultFailed(content=result)
        return ToolResultSuccess(content=result)

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        result = await terminal_read_screen(terminal_id)
        if result.startswith("错误"):
            return ToolResultFailed(content=result)
        return ToolResultSuccess(content=result)

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        result = await terminal_close(terminal_id)
        if result.startswith("错误"):
            return ToolResultFailed(content=result)
        return ToolResultSuccess(content=result)

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> FileContentMessage | ToolResultFailed:
        """读取文件内容"""
        return await asyncio.to_thread(read_file, filepath, show_line_numbers)

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> ToolResultSuccess | ToolResultFailed:
        """写入内容到文件"""
        return await asyncio.to_thread(write_file, filepath, content, override)

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> ToolResultSuccess | ToolResultFailed:
        """替换文件内容中的指定字符串"""
        return await asyncio.to_thread(
            replace_file_content, filepath, old, new, replace_times
        )

    async def list_files(self, dirpath: str) -> ToolResultSuccess | ToolResultFailed:
        """列出指定文件夹中的文件和子目录"""
        return await asyncio.to_thread(list_files, dirpath)

    async def get_absolute_path(
        self, path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """获取路径的绝对路径"""
        return await asyncio.to_thread(get_absolute_path, path)

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """执行sed表达式并返回输出"""
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        return await asyncio.to_thread(
            read_file_with_sed, expression, filepath, sandbox.wrap_argv
        )

    async def modify_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """使用sed表达式修改文件"""
        sandbox = self._registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        return await asyncio.to_thread(
            modify_file_with_sed, expression, filepath, sandbox.wrap_argv
        )

    async def get_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        """获取所有终端列表"""
        from .terminal import terminals

        if not terminals:
            return ToolResultSuccess(content="<<terminals>>没有活动的终端<<terminals>>")
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
        return ToolResultSuccess(content="\n".join(lines))

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        import os
        import pathlib

        if os.path.exists(remote_path):
            return ToolResultFailed(content=f"文件已存在: {remote_path}")
        try:
            pathlib.Path(remote_path).write_bytes(data)
            return ToolResultSuccess(content=f"文件已上传: {remote_path}")
        except Exception as e:
            return ToolResultFailed(content=f"上传文件失败: {e}")

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        import os
        import pathlib

        if not os.path.exists(remote_path):
            return ToolResultFailed(content=f"文件不存在: {remote_path}")
        try:
            data = pathlib.Path(remote_path).read_bytes()
            pathlib.Path(local_path).write_bytes(data)
            return ToolResultSuccess(content=f"文件已下载: {local_path}")
        except Exception as e:
            return ToolResultFailed(content=f"下载文件失败: {e}")
