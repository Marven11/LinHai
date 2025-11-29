"""命令执行工具模块，提供命令执行功能。"""

from datetime import datetime
import asyncio
import os
import signal
import subprocess
from linhai.tool.base import (
    global_tools,
    ToolArgInfo,
    ToolResultMessage,
    ToolErrorMessage,
)
import platform


def get_current_shell() -> str:
    """获取当前shell路径"""
    system = platform.system()
    if system == "Windows":
        return os.environ.get("COMSPEC", "cmd.exe")
    else:
        return os.environ.get("SHELL", "/bin/sh")


async def execute_command(
    command: str, timeout: float = 30.0
) -> ToolResultMessage | ToolErrorMessage:
    """执行系统命令并返回输出（内部函数）

    Args:
        command: 要执行的命令字符串
        timeout: 超时时间（秒），默认30秒

    Returns:
        命令执行的输出结果，包含returncode、stdout和stderr
    """
    if timeout > 3600:
        return ToolErrorMessage("Timeout value exceeds maximum limit of 3600 seconds")
    try:

        env = os.environ.copy()
        msg = "using env EDITOR failed, please use other tools."
        env["EDITOR"] = f"sh -c 'echo {msg!r}; exit 1'"

        process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
            start_new_session=True,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            returncode = process.returncode
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

            await process.wait()
            return ToolErrorMessage(
                f"Command timed out after {timeout} seconds, "
                "try to interact with it inside terminal"
            )

        stdout_str = stdout.decode("utf-8") if stdout else ""
        stderr_str = stderr.decode("utf-8") if stderr else ""

        output = f"""
Return code: {returncode}

Stdout:
{stdout_str}

Stderr:
{stderr_str}
"""
        if returncode == 0:
            return ToolResultMessage(output)
        else:
            return ToolErrorMessage(output)
    except (OSError, subprocess.SubprocessError) as e:
        return ToolErrorMessage(f"Command failed with error: {str(e)}")


@global_tools.register_tool(
    name="run_command",
    desc=f"执行系统命令。当前系统：{platform.system()}，当前shell：{get_current_shell()}。可以执行shell命令，但使用时务必谨慎，避免损坏用户电脑。",
    args={
        "command": ToolArgInfo(
            desc="要执行的命令字符串，如 'ls | grep test'", type="str"
        ),
        "timeout": ToolArgInfo(desc="超时时间（秒），默认30秒", type="float"),
    },
    required_args=["command"],
)
async def run_command(
    command: str, timeout: float = 30.0
) -> ToolResultMessage | ToolErrorMessage:
    """执行系统命令

    Args:
        command: 要执行的命令字符串，如 "ls | grep test"
        timeout: 超时时间（秒），默认30秒

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
def change_directory(directory: str) -> ToolResultMessage | ToolErrorMessage:
    """改变当前工作目录

    Args:
        directory: 目标目录的路径

    Returns:
        成功消息或错误信息
    """
    try:
        os.chdir(directory)
        return ToolResultMessage(f"Changed directory to: {directory}")
    except OSError as e:
        return ToolErrorMessage(f"Error changing directory: {str(e)}")


@global_tools.register_tool(
    name="sleep",
    desc="睡眠X秒，返回开始和结束时间",
    args={"seconds": ToolArgInfo(desc="睡眠的秒数", type="float")},
    required_args=["seconds"],
)
async def sleep_tool(seconds: float) -> ToolResultMessage:
    start = datetime.now()
    await asyncio.sleep(seconds)
    return ToolResultMessage(
        f"睡眠了{seconds} 秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )