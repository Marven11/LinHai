import os
import subprocess
from typing import Dict
from linhai.tool.base import register_tool, ToolArgInfo


@register_tool(
    name="run_command",
    desc="执行系统命令并返回输出",
    args={"command": ToolArgInfo(desc="要执行的命令字符串，如 'ls -l'", type="str")},
    required_args=["command"],
)
def run_command(command: str) -> str:
    """执行系统命令并返回输出

    Args:
        command: 要执行的命令字符串，如 "ls -l"

    Returns:
        命令执行的输出结果
    """
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,check=False
        )
        return f"""
{result.stdout}

------

{result.stderr}
"""
    except subprocess.CalledProcessError as e:
        return f"Command failed with error: {e.stderr}"


@register_tool(
    name="change_directory",
    desc="改变当前工作目录",
    args={"directory": ToolArgInfo(desc="目标目录的路径", type="str")},
    required_args=["directory"],
)
def change_directory(directory: str) -> str:
    """改变当前工作目录

    Args:
        directory: 目标目录的路径

    Returns:
        成功消息或错误信息
    """
    try:
        os.chdir(directory)
        return f"Changed directory to: {directory}"
    except Exception as e:
        return f"Error changing directory: {str(e)}"
