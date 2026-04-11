import asyncio
import re
import tempfile
import base64
import gzip
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
from .transport import TrojanTransport

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class _AsyncioProcessAdapter:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    @property
    def pid(self) -> str:
        return str(self._process.pid)

    async def stdio_write(self, content: str, with_enter: bool) -> ProcessWriteResult:
        if self._process.stdin is None:
            return ProcessWriteResult(pid=self.pid, success=False, error="stdin不可用")
        if with_enter:
            content += "\n"
        self._process.stdin.write(content.encode())
        await self._process.stdin.drain()
        return ProcessWriteResult(pid=self.pid, success=True, message="写入成功")

    async def stdio_read(
        self, wait_seconds: float, unescape_ansi: bool = True
    ) -> ProcessReadResult:
        if self._process.stdout is None:
            return ProcessReadResult(pid=self.pid, success=True, stdout="", stderr="")

        chunks: list[bytes] = []
        loop = asyncio.get_event_loop()
        start = loop.time()
        while loop.time() - start < wait_seconds:
            remaining = wait_seconds - (loop.time() - start)
            if remaining <= 0:
                break
            read_task = asyncio.ensure_future(self._process.stdout.read(4096))
            done, _ = await asyncio.wait({read_task}, timeout=min(0.5, remaining))
            if not done:
                read_task.cancel()
                if chunks:
                    break
                continue
            data = read_task.result()
            if data:
                chunks.append(data)
            else:
                break

        raw = b"".join(chunks).decode("utf-8", errors="replace")
        if unescape_ansi:
            raw = _ANSI_ESCAPE_RE.sub("", raw)
        exit_note = None
        if self._process.returncode is not None:
            exit_note = f"注意：当前程序{self.pid}已经退出\n"
        return ProcessReadResult(
            pid=self.pid, success=True, stdout=raw, stderr="", exit_note=exit_note
        )

    async def wait(self, timeout: float) -> ProcessWaitResult:
        wait_task = asyncio.ensure_future(self._process.wait())
        done, _ = await asyncio.wait({wait_task}, timeout=timeout)
        if not done:
            wait_task.cancel()
            return ProcessWaitResult(pid=self.pid, success=False, error="等待超时")
        returncode = wait_task.result()
        return ProcessWaitResult(
            pid=self.pid, success=True, returncode=returncode, stdout="", stderr=""
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult:
        if graceful:
            self._process.terminate()
            wait_task = asyncio.ensure_future(self._process.wait())
            done, _ = await asyncio.wait({wait_task}, timeout=5.0)
            if not done:
                wait_task.cancel()
                self._process.kill()
                await self._process.wait()
        else:
            self._process.kill()
            await self._process.wait()
        return ProcessKillResult(pid=self.pid, success=True, message="进程已终止")


class SshTrojanTransport:
    def __init__(
        self,
        host: str,
        registry: Registry,
        port: int = 22,
        username: Optional[str] = None,
    ):
        if username is None:
            import getpass

            username = getpass.getuser()

        self.host = host
        self.port = port
        self.username = username
        self.registry = registry
        self.trojan_path: Optional[Path] = None
        self.remote_trojan_path: Optional[str] = None
        self._trojan_transport: Optional[TrojanTransport] = None
        self._bash_process: Optional[Process] = None

        self.task_supervisor: TaskSupervisor = PlainTaskSupervisor()
        if registry.has_member("task_supervisor"):
            self.task_supervisor = registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )

    async def _execute_in_bash(
        self, command: str, timeout: float = 10.0
    ) -> tuple[int, str, str]:
        if self._bash_process is None:
            raise RuntimeError("Bash shell not started")

        marker = f"CMD_RESULT_{int(asyncio.get_event_loop().time())}"
        full_command = f'{{ {command}; }} 2>&1; echo "{marker}:$?"'

        write_result = await self._bash_process.stdio_write(
            full_command, with_enter=True
        )
        if not write_result.success:
            return 1, "", f"写入命令失败: {write_result.error}"

        output_lines = []
        result_line = None
        buffer = ""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            read_result = await self._bash_process.stdio_read(wait_seconds=1.0)
            if not read_result.success:
                break
            buffer += read_result.stdout
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
        exit_code, output, error = await self._execute_in_bash("python3 -V")
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

        exit_code, output, error = await self._execute_in_bash(command.strip())

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
        if self._bash_process is None:
            raise RuntimeError("Bash shell not started")
        command = f"python3 {remote_trojan_path}"
        write_result = await self._bash_process.stdio_write(command, with_enter=True)
        if not write_result.success:
            return False
        await asyncio.sleep(0.5)
        return True

    async def connect(self, process: Process) -> bool:
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"开始连接SSH服务器: {self.host}:{self.port}"
            ),
        )

        self.trojan_path = Path(tempfile.mktemp(suffix=".py"))
        trojan_file_path = Path(__file__).parent / "trojan.py"
        if not trojan_file_path.exists():
            raise FileNotFoundError(f"trojan.py文件不存在: {trojan_file_path}")
        trojan_content = trojan_file_path.read_text(encoding="utf-8")
        self.trojan_path.write_text(trojan_content, encoding="utf-8")

        self._bash_process = process

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"检查远程机器Python版本: {self.host}:{self.port}",
            ),
        )

        if not await self._check_python_version():
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content=f"远程机器Python版本检查失败: {self.host}:{self.port}",
                ),
            )
            await self._cleanup()
            return False

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"Python版本检查通过: {self.host}:{self.port}"
            ),
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"复制控制程序到远程机器: {self.host}:{self.port}",
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
                content=f"控制程序已复制到远程机器: {self.host}:{self.port}",
            ),
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"启动远程控制程序: {self.host}:{self.port}"
            ),
        )

        if not await self._start_trojan_process(remote_trojan_path):
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content=f"启动远程控制程序失败: {self.host}:{self.port}",
                ),
            )
            await self._cleanup()
            return False

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"远程控制程序启动成功: {self.host}:{self.port}",
            ),
        )

        self._trojan_transport = TrojanTransport(
            registry=self.registry,
            process=self._bash_process,
        )
        self._trojan_transport.start_reading()
        return True

    async def _cleanup(self):
        if self._bash_process:
            await self._bash_process.kill(graceful=True)

        if self.trojan_path and self.trojan_path.exists():
            self.trojan_path.unlink(missing_ok=True)

        self._bash_process = None
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
