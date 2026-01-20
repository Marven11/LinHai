"""Master host control module for tools that interact with the local machine."""

import asyncio
import time
from typing import Optional, Union
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.llm import Message
from linhai.agent.base import FileContentMessage

from .http import http_request
from .command import change_directory
from .terminal import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
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


class MasterHostControl:
    """本地主机控制类，负责提供本地机器工具的实现。

    注意：此类只提供工具方法的实现，不管理工具定义。
    工具定义由MachineControl统一管理。
    """

    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None,
        follow_redirects: bool = True,
        timeout: int = 60,
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送HTTP请求并返回响应内容或文件路径"""
        return await http_request(
            method, url, params, headers, data, follow_redirects, timeout
        )

    async def process_create(
        self, command: list[str], wait_second: float = 1.0
    ) -> ToolResultSuccess | ToolResultFailed:
        """创建一个进程，等待一段时间后检查状态"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            pid = str(process.pid)
            self._processes[pid] = process

            start = time.perf_counter()
            while time.perf_counter() - start < wait_second:
                await asyncio.sleep(0.1)
                if process.returncode is not None:
                    break

            if process.returncode is not None:
                del self._processes[pid]
                stdout_data, stderr_data = b"", b""
                if process.stdout:
                    stdout_data = await process.stdout.read()
                if process.stderr:
                    stderr_data = await process.stderr.read()

                stdout_str = stdout_data.decode("utf-8", errors="replace")
                stderr_str = stderr_data.decode("utf-8", errors="replace")
                return ToolResultSuccess(
                    content=f"<<pid>>{pid}<<pid>><<returncode>>{process.returncode}<<returncode>><<stdout>>{stdout_str}<<stdout>><<stderr>>{stderr_str}<<stderr>>"
                )
            else:
                return ToolResultSuccess(
                    content=f"<<pid>>{pid}<<pid>><<message>>程序仍然在运行<<message>>"
                )
        except Exception as e:
            return ToolResultFailed(content=str(e))

    async def process_stdio_write(
        self, pid: str, content: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """向进程的标准输入写入内容"""
        try:
            process = self._processes.get(pid)
            if process is None:
                return ToolResultFailed(content=f"找不到进程 {pid}")
            if process.stdin is None:
                return ToolResultFailed(content=f"进程 {pid} 没有标准输入")
            process.stdin.write(content.encode("utf-8"))
            await process.stdin.drain()
            return ToolResultSuccess(
                content=f"<<pid>>{pid}<<pid>><<message>>写入成功<<message>>"
            )
        except Exception as e:
            return ToolResultFailed(content=str(e))

    async def process_stdio_read(
        self, pid: str, unescape_ansi: bool = True
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取进程的标准输出和标准错误内容"""
        try:
            process = self._processes.get(pid)
            if process is None:
                return ToolResultFailed(content=f"找不到进程 {pid}")
            stdout_data, stderr_data = b"", b""
            if process.stdout:
                stdout_data = await process.stdout.read(8 * 1024)
            if process.stderr:
                stderr_data = await process.stderr.read(8 * 1024)
            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")
            if unescape_ansi:
                import re

                ansi_escape = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
                stdout_str = ansi_escape.sub("", stdout_str)
                stderr_str = ansi_escape.sub("", stderr_str)
            return ToolResultSuccess(
                content=f"<<pid>>{pid}<<pid>><<stdout>>{stdout_str}<<stdout>><<stderr>>{stderr_str}<<stderr>>"
            )
        except Exception as e:
            return ToolResultFailed(content=str(e))

    async def process_wait(
        self, pid: str, timeout: float
    ) -> ToolResultSuccess | ToolResultFailed:
        """等待进程结束，带超时设置"""
        try:
            if timeout > 3600:
                return ToolResultFailed(content="超时时间不能超过3600秒")
            process = self._processes.get(pid)
            if process is None:
                return ToolResultFailed(content=f"找不到进程 {pid}")
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
                stdout_data, stderr_data = b"", b""
                if process.stdout:
                    stdout_data = await process.stdout.read()
                if process.stderr:
                    stderr_data = await process.stderr.read()
                stdout_str = stdout_data.decode("utf-8", errors="replace")
                stderr_str = stderr_data.decode("utf-8", errors="replace")
                del self._processes[pid]
                return ToolResultSuccess(
                    content=f"<<pid>>{pid}<<pid>><<returncode>>{process.returncode}<<returncode>><<stdout>>{stdout_str}<<stdout>><<stderr>>{stderr_str}<<stderr>>"
                )
            except asyncio.TimeoutError:
                return ToolResultFailed(content=f"等待进程 {pid} 超时")
        except Exception as e:
            return ToolResultFailed(content=str(e))

    async def process_kill(
        self, pid: str, graceful: bool = True
    ) -> ToolResultSuccess | ToolResultFailed:
        """杀死进程，可选择优雅终止"""
        try:
            process = self._processes.get(pid)
            if process is None:
                return ToolResultFailed(
                    content="找不到进程，必须传入当前工具组创建的PID"
                )
            if graceful:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            else:
                process.kill()
                await process.wait()
            del self._processes[pid]
            return ToolResultSuccess(
                content=f"<<pid>>{pid}<<pid>><<message>>进程已终止<<message>>"
            )
        except Exception as e:
            return ToolResultFailed(content=str(e))

    async def change_directory(
        self, directory: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """改变当前工作目录"""
        return change_directory(directory)

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed:
        """新建虚拟终端"""
        return await terminal_create(columns, lines)

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送按键列表到终端"""
        return await terminal_send_keys(terminal_id, keys)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送命令等字符串到终端"""
        return await terminal_send_string(terminal_id, string, with_enter, wait_seconds)

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取终端屏幕内容"""
        return await terminal_read_screen(terminal_id)

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """关闭终端"""
        return await terminal_close(terminal_id)

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
        return await asyncio.to_thread(read_file_with_sed, expression, filepath)

    async def modify_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """使用sed表达式修改文件"""
        return await asyncio.to_thread(modify_file_with_sed, expression, filepath)

    async def get_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        """获取所有终端列表"""
        from .terminal import terminals

        if not terminals:
            return ToolResultSuccess(content="<<terminals>>没有活动的终端<<terminals>>")
        lines = []
        for term_id, terminal in terminals.items():
            # 获取终端状态信息
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
