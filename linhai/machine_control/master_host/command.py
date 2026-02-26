"""命令执行工具模块，提供命令执行和目录切换功能。"""

import asyncio
import os
import platform  # pylint: disable=unused-import
import signal
import subprocess

from linhai.tool.base import ToolResultSuccess, ToolResultFailed


def change_directory(directory: str) -> ToolResultSuccess | ToolResultFailed:
    """改变当前工作目录"""
    try:
        old_dir = os.getcwd()
    except FileNotFoundError:
        old_dir = None
    except OSError as e:
        return ToolResultFailed(content=f"Error getting current directory: {str(e)}")

    try:
        os.chdir(directory)
    except OSError as e:
        return ToolResultFailed(content=f"Error changing directory: {str(e)}")

    if old_dir is None:
        return ToolResultSuccess(content=f"原目录不存在，切换到了{directory}")
    else:
        return ToolResultSuccess(content=f"从目录{old_dir}切换到了{directory}")
