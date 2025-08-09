import subprocess
from typing import Dict
from linhai.tool.base import register_tool, ToolArgInfo


@register_tool(
    name="run_command",
    desc="执行系统命令并返回输出",
    args={"command": ToolArgInfo(desc="要执行的命令字符串，如 'ls -l'", type=str)},
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
