"""Master host control module for tools that interact with the local machine."""

import asyncio
from typing import Optional
from linhai.tool.base import ToolErrorMessage
from linhai.llm import Message
from linhai.agent.base import FileContentMessage

from .http import http_request
from .command import run_command, change_directory
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
    append_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    read_file_with_sed,
    modify_file_with_sed,
    insert_at_line,
)


class MasterHostControl:
    """本地主机控制类，负责提供本地机器工具的实现。

    注意：此类只提供工具方法的实现，不管理工具定义。
    工具定义由MachineControl统一管理。
    """

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[str] = None,
        follow_redirects: bool = True,
        timeout: int = 60,
    ) -> Message:
        """发送HTTP请求并返回响应内容或文件路径"""
        return await http_request(method, url, params, headers, data, follow_redirects, timeout)

    async def run_command(self, command: str, timeout: float = 30.0) -> Message:
        """执行系统命令"""
        return await run_command(command, timeout)

    async def change_directory(self, directory: str) -> Message:
        """改变当前工作目录"""
        return change_directory(directory)

    async def terminal_create(self, columns: int = 80, lines: int = 24) -> Message:
        """新建虚拟终端"""
        return await terminal_create(columns, lines)

    async def terminal_send_keys(self, terminal_id: str, keys: list[str]) -> Message:
        """发送按键列表到终端"""
        return await terminal_send_keys(terminal_id, keys)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> Message:
        """发送命令等字符串到终端"""
        return await terminal_send_string(
            terminal_id, string, with_enter, wait_seconds
        )

    async def terminal_read_screen(self, terminal_id: str) -> Message:
        """读取终端屏幕内容"""
        return await terminal_read_screen(terminal_id)

    async def terminal_close(self, terminal_id: str) -> Message:
        """关闭终端"""
        return await terminal_close(terminal_id)

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> FileContentMessage | ToolErrorMessage:
        """读取文件内容"""
        return await asyncio.to_thread(read_file, filepath, show_line_numbers)

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> Message:
        """写入内容到文件"""
        return await asyncio.to_thread(write_file, filepath, content, override)

    async def append_file(
        self, filepath: str, content: str, assume_empty_line: bool = True
    ) -> Message:
        """追加内容到文件末尾"""
        return await asyncio.to_thread(
            append_file, filepath, content, assume_empty_line
        )

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> Message:
        """替换文件内容中的指定字符串"""
        return await asyncio.to_thread(
            replace_file_content, filepath, old, new, replace_times
        )

    async def list_files(self, dirpath: str) -> Message:
        """列出指定文件夹中的文件和子目录"""
        return await asyncio.to_thread(list_files, dirpath)

    async def get_absolute_path(self, path: str) -> Message:
        """获取路径的绝对路径"""
        return await asyncio.to_thread(get_absolute_path, path)

    async def read_file_with_sed(self, expression: str, filepath: str) -> Message:
        """执行sed表达式并返回输出"""
        return await asyncio.to_thread(read_file_with_sed, expression, filepath)

    async def modify_file_with_sed(self, expression: str, filepath: str) -> Message:
        """使用sed表达式修改文件"""
        return await asyncio.to_thread(modify_file_with_sed, expression, filepath)

    async def insert_at_line(
        self,
        filepath: str,
        line_number: int,
        content: str,
        expected_line_content: str,
    ) -> Message:
        """将内容插入到文件的指定行号位置"""
        return await asyncio.to_thread(
            insert_at_line, filepath, line_number, content, expected_line_content
        )
