import asyncio
import base64
import gzip
import uuid
from pathlib import Path
from typing import Optional

from linhai.machine_control.master_host.process import LocalPtyProcess
from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.machine_control.process import Process
from rich.text import Text


def _strip_ansi_and_cr(text: str) -> str:
    return Text.from_ansi(text).plain.replace("\r", "")


def _split_marker_for_echo(marker: str) -> str:
    mid = len(marker) // 2
    return marker[:mid] + '""' + marker[mid:]


def _is_pty_process(process: Process) -> bool:
    return isinstance(process, LocalPtyProcess)


async def _disable_pty_echo(process: Process) -> None:
    if not _is_pty_process(process):
        return
    await process.stdio_write("stty -echo", with_enter=True)
    await asyncio.sleep(0.3)
    await process.stdio_read(0.5)


async def _execute_in_shell(
    process: Process, command: str, timeout: float = 10.0
) -> tuple[int, str, str]:
    marker_hex = uuid.uuid4().hex[:4]
    marker_open = f"<linhai_cmd_{marker_hex}>"
    marker_close = f"</linhai_cmd_{marker_hex}>"

    marker_open_echo = _split_marker_for_echo(marker_open)
    marker_close_echo = _split_marker_for_echo(marker_close)

    full_command = (
        f'echo "{marker_open_echo}"; '
        f"{{ {command}; }} 2>&1; "
        f'RC=$?; echo "${{RC}}{marker_close_echo}"'
    )

    write_result = await process.stdio_write(full_command, with_enter=True)
    if not write_result.success:
        return 1, "", f"写入命令失败: {write_result.error}"

    buffer = ""
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < timeout:
        read_result = await process.stdio_read(wait_seconds=1.0)
        if not read_result.success:
            break
        decoded = read_result.stdout.decode("utf-8", errors="replace")
        buffer += _strip_ansi_and_cr(decoded)

        newline_prefix = f"\n{marker_open}"
        start_idx = buffer.find(newline_prefix)
        if start_idx != -1:
            start_idx += 1
        else:
            start_idx = buffer.find(marker_open)
        if start_idx == -1:
            continue
        close_idx = buffer.find(marker_close, start_idx)
        if close_idx == -1:
            continue

        content = buffer[start_idx + len(marker_open) : close_idx]
        lines = content.strip().split("\n")
        last_line = lines[-1].strip()
        if last_line.isdigit():
            exit_code = int(last_line)
            output_lines = lines[:-1]
        else:
            exit_code = 1
            output_lines = lines

        return exit_code, "\n".join(output_lines).strip(), ""

    return 1, "", "命令执行超时"


async def _upload_trojan_chunked(
    process: Process, encoded_content: str
) -> tuple[int, str, str]:
    exit_code, output, error = await _execute_in_shell(
        process, "B64_PATH=$(mktemp --suffix=.b64) && echo $B64_PATH"
    )
    if exit_code != 0:
        return exit_code, output, error
    b64_path = output.strip()

    chunk_size = 1024
    for i in range(0, len(encoded_content), chunk_size):
        chunk = encoded_content[i : i + chunk_size]
        exit_code, output, error = await _execute_in_shell(
            process, f"echo '{chunk}' >> \"{b64_path}\""
        )
        if exit_code != 0:
            return exit_code, output, error

    exit_code, output, error = await _execute_in_shell(
        process,
        f"REMOTE_TEMP_PATH=$(mktemp --suffix=.py) && "
        f'base64 -d "{b64_path}" | gzip -d > "$REMOTE_TEMP_PATH" && '
        f'rm "{b64_path}" && '
        f'echo "$REMOTE_TEMP_PATH"',
    )
    return exit_code, output, error


async def setup_trojan_in_shell(
    process: Process, registry: Registry
) -> Optional[tuple[str, str]]:
    await registry.send_if_exists(
        "ui_log",
        UiNotice(level="INFO", content="开始连接远程机器"),
    )

    await _disable_pty_echo(process)

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

    if _is_pty_process(process):
        exit_code, output, error = await _upload_trojan_chunked(
            process, encoded_content
        )
    else:
        command = (
            "REMOTE_TEMP_PATH=$(mktemp --suffix=.py) && "
            f"echo '{encoded_content}' | base64 -d | gzip -d > \"$REMOTE_TEMP_PATH\" && "
            'echo "$REMOTE_TEMP_PATH"'
        )
        exit_code, output, error = await _execute_in_shell(process, command)

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

    marker_hex = uuid.uuid4().hex[:4]
    start_command = f"python3 {remote_path} {marker_hex}"
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

    return remote_path, marker_hex
