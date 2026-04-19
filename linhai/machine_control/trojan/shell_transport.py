import asyncio
import base64
import gzip
from pathlib import Path
from typing import Optional

from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.machine_control.process import Process


async def _execute_in_shell(
    process: Process, command: str, timeout: float = 10.0
) -> tuple[int, str, str]:
    marker = f"CMD_RESULT_{int(asyncio.get_event_loop().time())}"
    full_command = f'{{ {command}; }} 2>&1; echo "{marker}:$?"'

    from rich.text import Text

    write_result = await process.stdio_write(full_command, with_enter=True)
    if not write_result.success:
        return 1, "", f"写入命令失败: {write_result.error}"

    output_lines = []
    result_line = None
    buffer = ""
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < timeout:
        read_result = await process.stdio_read(wait_seconds=1.0)
        if not read_result.success:
            break
        decoded = read_result.stdout.decode("utf-8", errors="replace")
        text = Text.from_ansi(decoded).plain
        if decoded.endswith("\n"):
            text += "\n"
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip()
            if line.startswith(f"{marker}:"):
                result_line = line
                break
            output_lines.append(line)
        if result_line is not None:
            break

    if result_line is None:
        return 1, "", "命令执行超时"

    parts = result_line.split(":", 1)
    if len(parts) != 2:
        exit_code = 1
    else:
        exit_code_str = parts[1]
        if exit_code_str.isdigit():
            exit_code = int(exit_code_str)
        else:
            exit_code = 1

    return exit_code, "\n".join(output_lines), ""


async def setup_trojan_in_shell(process: Process, registry: Registry) -> Optional[str]:
    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="开始连接远程机器"),
    )

    trojan_file_path = Path(__file__).parent / "trojan.py"
    if not trojan_file_path.exists():
        raise FileNotFoundError(f"trojan.py文件不存在: {trojan_file_path}")

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="检查远程机器Python版本"),
    )

    exit_code, output, error = await _execute_in_shell(process, "python3 -V")
    if exit_code != 0 or "Python 3" not in output:
        await registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="ERROR", content=f"检查远程Python版本失败: {output or error}"
            ),
        )
        return None

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="Python版本检查通过"),
    )

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="复制控制程序到远程机器"),
    )

    trojan_content = trojan_file_path.read_text(encoding="utf-8")
    compressed = gzip.compress(trojan_content.encode())
    encoded_content = base64.b64encode(compressed).decode()

    command = f"""
    REMOTE_TEMP_PATH=$(mktemp --suffix=.py) && \
    echo '{encoded_content}' | base64 -d | gzip -d > "$REMOTE_TEMP_PATH" && \
    echo "$REMOTE_TEMP_PATH"
    """

    exit_code, output, error = await _execute_in_shell(process, command.strip())
    if exit_code != 0:
        error_msg = error or "创建远程临时文件失败"
        await registry.send_if_exists(
            "ui_log",
            UiNotice(level="ERROR", content=f"创建远程临时文件失败: {error_msg}"),
        )
        return None

    remote_path = output.strip()

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="控制程序已复制到远程机器"),
    )

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="启动远程控制程序"),
    )

    start_command = f"python3 {remote_path}"
    write_result = await process.stdio_write(start_command, with_enter=True)
    if not write_result.success:
        await registry.send_if_exists(
            "ui_log",
            UiNotice(level="ERROR", content="启动远程控制程序失败"),
        )
        return None

    await asyncio.sleep(0.5)

    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="远程控制程序启动成功"),
    )

    return remote_path
