"""命令执行工具模块，提供命令执行和目录切换功能。"""

import asyncio
import os
import platform  # pylint: disable=unused-import
import signal
import subprocess

from linhai.tool.base import ToolResultMessage, ToolErrorMessage


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
        # 防止用户使用EDITOR环境变量打开编辑器
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
