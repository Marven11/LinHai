"""命令执行工具模块，提供安全命令执行功能。"""

import os
import subprocess
import re
from linhai.tool.base import register_tool, ToolArgInfo


def execute_command(command: str, timeout: float = 2.0) -> str:
    """执行系统命令并返回输出（内部函数）

    Args:
        command: 要执行的命令字符串
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果
    """
    if timeout > 600:
        return "Timeout value exceeds maximum limit of 600 seconds"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return f"""
{result.stdout}

------

{result.stderr}
"""
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except subprocess.CalledProcessError as e:
        return f"Command failed with error: {e.stderr}"


def validate_simple_command(command: str) -> bool:
    """验证命令是否简单安全（白名单验证）

    Args:
        command: 命令字符串

    Returns:
        True如果命令安全，False如果包含危险模式
    """
    # 检查命令注入模式：$() 和 ``
    if re.search(r"\$\s*\([^)]+\)", command) or re.search(r"`[^`]+`", command):
        return False

    # 提取第一个单词（命令名）
    parts = command.strip().split()
    if not parts:
        return False
    command_name = parts[0]

    # 检查命令名是否只包含允许的字符：字母、数字、横杠、下划线
    if not re.fullmatch(r"[a-zA-Z0-9\-_]+", command_name):
        return False

    return True


@register_tool(
    name="run_simple_command",
    desc="执行简单系统命令（白名单验证），只允许安全命令",
    args={
        "command": ToolArgInfo(desc="要执行的命令字符串，如 'ls -l'", type="str"),
        "timeout": ToolArgInfo(desc="超时时间（秒），默认2秒", type="float"),
    },
    required_args=["command"],
)
def run_simple_command(command: str, timeout: float = 2.0) -> str:
    """执行简单系统命令（白名单验证），只允许安全命令

    Args:
        command: 要执行的命令字符串，如 "ls -l"
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果或错误信息
    """
    if not validate_simple_command(command):
        return "Error: Command contains dangerous patterns or invalid command name."

    return execute_command(command, timeout)


@register_tool(
    name="run_complex_command",
    desc="执行复杂系统命令（可能包含危险操作，请谨慎使用）",
    args={
        "command": ToolArgInfo(
            desc="要执行的命令字符串，如 'ls | grep test'", type="str"
        ),
        "timeout": ToolArgInfo(desc="超时时间（秒），默认2秒", type="float"),
    },
    required_args=["command"],
)
def run_complex_command(command: str, timeout: float = 2.0) -> str:
    """执行复杂系统命令（可能包含危险操作，请谨慎使用）

    Args:
        command: 要执行的命令字符串，如 "ls | grep test"
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果
    """
    return execute_command(command, timeout)


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
    except OSError as e:
        return f"Error changing directory: {str(e)}"


@register_tool(
    name="show_git_changes",
    desc="显示git修改，通过展示git的输出展示文件什么地方被修改",
    args={
        "filepath": ToolArgInfo(
            desc="文件路径，必须指定", type="str"
        ),
    },
    required_args=["filepath"],
)
def show_git_changes(filepath: str = "") -> str:
    """显示git修改，展示文件的修改内容。

    Args:
        filepath: 文件路径(可选)，不指定则显示所有修改

    Returns:
        git diff输出或错误消息
    """
    try:
        # 构建git diff命令
        if filepath:
            cmd = f"git diff -- {filepath}"
        else:
            cmd = "git diff"

        # 执行git diff命令
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            if "not a git repository" in result.stderr:
                return "当前目录不是git仓库"
            return f"git命令执行错误: {result.stderr}"

        if not result.stdout.strip():
            if filepath:
                return f"文件{filepath!r}没有未暂存的修改"
            else:
                return "没有未暂存的修改"

        return result.stdout

    except subprocess.TimeoutExpired:
        return "git命令执行超时"
    except Exception as e:
        return f"执行git命令时发生错误: {str(e)}"
