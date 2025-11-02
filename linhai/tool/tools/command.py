"""命令执行工具模块，提供安全命令执行功能。"""

import asyncio
import os
import subprocess
import re
from linhai.tool.base import global_tools, ToolArgInfo
# import sys  # Unused import
import platform

VALIDATE_COMMAND_REGEX = re.compile(r'^[-a-zA-Z0-9_ /*=+\'"<> \.]+$')


async def execute_command(command: str, timeout: float = 2.0) -> str:
    """执行系统命令并返回输出（内部函数）

    Args:
        command: 要执行的命令字符串
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果，包含returncode、stdout和stderr
    """
    if timeout > 3600:
        return "Timeout value exceeds maximum limit of 3600 seconds"
    try:
        # 设置EDITOR环境变量为输出错误并退出
        env = os.environ.copy()
        msg = "using env EDITOR failed, please use other tools."
        env['EDITOR'] = f'sh -c \'echo {msg!r}; exit 1\''
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            returncode = process.returncode
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Command timed out after {timeout} seconds"

        stdout_str = stdout.decode("utf-8") if stdout else ""
        stderr_str = stderr.decode("utf-8") if stderr else ""

        return f"""
Return code: {returncode}

Stdout:
{stdout_str}

Stderr:
{stderr_str}
"""
    except (OSError, subprocess.SubprocessError) as e:
        return f"Command failed with error: {str(e)}"


def validate_simple_command(command: str) -> bool:
    """验证命令是否简单安全（白名单验证）

    Args:
        command: 命令字符串

    Returns:
        True如果命令安全，False如果包含危险模式
    """
    return VALIDATE_COMMAND_REGEX.fullmatch(command) is not None


@global_tools.register_tool(
    name="run_simple_command",
    desc=f"执行简单系统命令（白名单验证）。当前系统：{platform.system()}。可以执行常见的shell命令，但使用时不要损坏用户的电脑。",
    args={
        "command": ToolArgInfo(desc="要执行的命令字符串，如 'ls -l'", type="str"),
        "timeout": ToolArgInfo(desc="超时时间（秒），默认2秒", type="float"),
    },
    required_args=["command"],
)
async def run_simple_command(command: str, timeout: float = 2.0) -> str:
    """执行简单系统命令（白名单验证），只允许安全命令

    Args:
        command: 要执行的命令字符串，如 "ls -l"
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果或错误信息
    """
    if not validate_simple_command(command):
        return (
            f"错误：命令包含不允许的字符，应符合这个正则{VALIDATE_COMMAND_REGEX.pattern}"
            "如果需要使用其他字符，请使用run_complex_command工具。"
        )

    return await execute_command(command, timeout)


@global_tools.register_tool(
    name="run_complex_command",
    desc=f"执行复杂系统命令（可能包含危险操作）。当前系统：{platform.system()}。可以执行常见的shell命令，但使用时务必谨慎，避免损坏用户电脑。",
    args={
        "command": ToolArgInfo(
            desc="要执行的命令字符串，如 'ls | grep test'", type="str"
        ),
        "timeout": ToolArgInfo(desc="超时时间（秒），默认2秒", type="float"),
    },
    required_args=["command"],
)
async def run_complex_command(command: str, timeout: float = 2.0) -> str:
    """执行复杂系统命令（可能包含危险操作，请谨慎使用）

    Args:
        command: 要执行的命令字符串，如 "ls | grep test"
        timeout: 超时时间（秒），默认2秒

    Returns:
        命令执行的输出结果
    """
    return await execute_command(command, timeout)


@global_tools.register_tool(
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

