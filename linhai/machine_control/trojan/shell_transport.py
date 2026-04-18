import asyncio
import tempfile
import base64
import gzip
import getpass
from pathlib import Path
from typing import Dict, Any, Optional

from linhai.registry import Registry
from linhai.task_supervisor import PlainTaskSupervisor, TaskSupervisor
from linhai.utils.common import UiNotice
from linhai.machine_control.process import (
    Process,
    ProcessKillResult,
    ProcessReadResult,
    ProcessWriteResult,
    ProcessWaitResult,
)
from rich.text import Text
from .transport import TrojanTransport


class ShellTrojanTransport:
    def __init__(
        self,
        registry: Registry,
        process: Process,
    ):
        self.registry = registry
        self._shell_process = process
        self.trojan_path: Optional[Path] = None
        self.remote_trojan_path: Optional[str] = None
        self._trojan_transport: Optional[TrojanTransport] = None

        self.task_supervisor: TaskSupervisor = PlainTaskSupervisor()
        if registry.has_member("task_supervisor"):
            self.task_supervisor = registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )

    async def _execute_in_shell(
        self, command: str, timeout: float = 10.0
    ) -> tuple[int, str, str]:
        marker = f"CMD_RESULT_{int(asyncio.get_event_loop().time())}"
        full_command = f'{{ {command}; }} 2>&1; echo "{marker}:$?"'

        write_result = await self._shell_process.stdio_write(
            full_command, with_enter=True
        )
        if not write_result.success:
            return 1, "", f"写入命令失败: {write_result.error}"

        output_lines = []
        result_line = None
        buffer = ""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            read_result = await self._shell_process.stdio_read(wait_seconds=1.0)
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

    async def _check_python_version(self) -> bool:
        exit_code, output, error = await self._execute_in_shell("python3 -V")
        if exit_code != 0 or "Python 3" not in output:
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR", content=f"检查远程Python版本失败: {output or error}"
                ),
            )
            return False
        return True

    async def _copy_trojan_to_remote(self) -> Optional[str]:
        if self.trojan_path is None or not self.trojan_path.exists():
            raise FileNotFoundError("本地trojan临时文件不存在")

        trojan_content = self.trojan_path.read_text(encoding="utf-8")

        compressed = gzip.compress(trojan_content.encode())
        encoded_content = base64.b64encode(compressed).decode()

        command = f"""
        REMOTE_TEMP_PATH=$(mktemp --suffix=.py) && \
        echo '{encoded_content}' | base64 -d | gzip -d > "$REMOTE_TEMP_PATH" && \
        echo "$REMOTE_TEMP_PATH"
        """

        exit_code, output, error = await self._execute_in_shell(command.strip())

        if exit_code != 0:
            error_msg = error or "创建远程临时文件失败"
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="ERROR", content=f"创建远程临时文件失败: {error_msg}"),
            )
            return None

        remote_path = output.strip()
        return remote_path

    async def _start_trojan_process(self, remote_trojan_path: str) -> bool:
        command = f"python3 {remote_trojan_path}"
        write_result = await self._shell_process.stdio_write(command, with_enter=True)
        if not write_result.success:
            return False
        await asyncio.sleep(0.5)
        return True

    async def connect(self) -> bool:
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="开始连接远程机器"),
        )

        self.trojan_path = Path(tempfile.mktemp(suffix=".py"))
        trojan_file_path = Path(__file__).parent / "trojan.py"
        if not trojan_file_path.exists():
            raise FileNotFoundError(f"trojan.py文件不存在: {trojan_file_path}")
        trojan_content = trojan_file_path.read_text(encoding="utf-8")
        self.trojan_path.write_text(trojan_content, encoding="utf-8")

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="检查远程机器Python版本",
            ),
        )

        if not await self._check_python_version():
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content="远程机器Python版本检查失败",
                ),
            )
            await self._cleanup()
            return False

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="Python版本检查通过"),
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="复制控制程序到远程机器",
            ),
        )

        remote_trojan_path = await self._copy_trojan_to_remote()
        if remote_trojan_path is None:
            await self._cleanup()
            return False
        self.remote_trojan_path = remote_trojan_path

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="控制程序已复制到远程机器",
            ),
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="启动远程控制程序"),
        )

        if not await self._start_trojan_process(remote_trojan_path):
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content="启动远程控制程序失败",
                ),
            )
            await self._cleanup()
            return False

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content="远程控制程序启动成功",
            ),
        )

        self._trojan_transport = TrojanTransport(
            registry=self.registry,
            process=self._shell_process,
        )
        self._trojan_transport.start_reading()
        return True

    async def _cleanup(self):
        if self.trojan_path and self.trojan_path.exists():
            self.trojan_path.unlink(missing_ok=True)

        self._trojan_transport = None

    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._trojan_transport is None:
            raise ConnectionError("未建立连接")
        return await self._trojan_transport.send_request(method, params)

    async def disconnect(self):
        if self._trojan_transport:
            await self._trojan_transport.disconnect()
        await self._cleanup()

    def is_connected(self) -> bool:
        return (
            self._trojan_transport is not None and self._trojan_transport.is_connected()
        )

    async def wait_for_disconnect(self):
        if self._trojan_transport:
            await self._trojan_transport.wait_for_disconnect()
