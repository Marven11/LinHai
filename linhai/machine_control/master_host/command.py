"""命令执行工具模块，提供命令执行和目录切换功能。"""

import asyncio
import os
import platform  # pylint: disable=unused-import
import signal
import subprocess

from linhai.tool.base import ToolResultSuccess, ToolResultFailed


def change_directory(directory: str) -> ToolResultSuccess | ToolResultFailed:
    """改变当前工作目录

    Args:
        directory: 目标目录的路径

    Returns:
         成功消息或错误信息
    """
    try:
        os.chdir(directory)
        return ToolResultSuccess(content=f"Changed directory to: {directory}")
    except OSError as e:
        return ToolResultFailed(content=f"Error changing directory: {str(e)}")
