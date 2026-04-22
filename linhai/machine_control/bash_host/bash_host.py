"""BashHostControl: 通过raw bash命令控制远程机器。"""

import asyncio
import shlex
from typing import Any, Dict, Optional, Union

from linhai.agent.messages import FileContentMessage
from linhai.machine_control.http_message import HttpMessage
from linhai.machine_control.process import (
    Process,
    ProcessCreateResult,
    ProcessCreateInfo,
)
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils.common import UiNotice
from .file import (
    read_file as _read_file,
    write_file as _write_file,
    replace_file_content as _replace_file_content,
    list_files as _list_files,
    get_absolute_path as _get_absolute_path,
    read_file_with_sed as _read_file_with_sed,
)
from .process import BashProcess
from . import terminal as _terminal


class BashHostControl:
    """通过raw bash命令控制远程机器，不依赖远程Python环境。"""

    GLOBAL_TIMEOUT = 30.0
    MARKER_PREFIX = "_LINHAI_CMD_RESULT_"

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self._machine_id: str = ""
        self._shell_process: Optional[Process] = None
        self._tmp_dir: str = ""
        self._encoding: str = "utf-8"
        self._counter: int = 0
        self._timeout_mode: str = "builtin"
        self._processes: dict[str, BashProcess] = {}

    def make_temp_path(self, prefix: str) -> str:
        self._counter += 1
        return f"{self._tmp_dir}/{prefix}_{self._counter}"

    def _next_marker(self) -> str:
        self._counter += 1
        return f"{self.MARKER_PREFIX}{self._counter}"

    async def connect(self, process: Process) -> bool:
        self._shell_process = process

        rc, stdout, stderr = await self.execute_raw(
            "TMPDIR=$(mktemp -d /tmp/linhai_bash_XXXXXX) && echo $TMPDIR && echo $TMPDIR > $TMPDIR/.dir"
        )
        if rc != 0:
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="ERROR", content=f"创建远程临时目录失败: {stderr}"),
            )
            return False
        self._tmp_dir = stdout.strip()

        rc, stdout, stderr = await self.execute_raw("echo $LANG")
        if rc == 0 and stdout.strip():
            lang = stdout.strip().lower()
            if "utf-8" in lang or "utf8" in lang:
                self._encoding = "utf-8"
            else:
                self._encoding = "ascii"
        else:
            self._encoding = "ascii"

        rc, stdout, _ = await self.execute_raw(
            "timeout --version 2>/dev/null && echo HAS_TIMEOUT"
        )
        if rc == 0 and "HAS_TIMEOUT" in stdout:
            self._timeout_mode = "timeout"
        else:
            rc, _, _ = await self.execute_raw("perl -e 'print 1' 2>/dev/null")
            if rc == 0:
                self._timeout_mode = "perl"
            else:
                self._timeout_mode = "builtin"

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"Bash控制连接成功 (编码: {self._encoding}, timeout: {self._timeout_mode}, 临时目录: {self._tmp_dir})",
            ),
        )
        return True

    async def execute_raw(
        self, command: str, timeout: float = 0.0
    ) -> tuple[int, str, str]:
        if self._shell_process is None:
            return 1, "", "未建立连接"

        shell_proc = self._shell_process
        effective_timeout = timeout if timeout > 0 else self.GLOBAL_TIMEOUT
        marker = self._next_marker()
        quoted_cmd = shlex.quote(command)

        timeout_secs = int(effective_timeout)
        if self._timeout_mode == "timeout":
            full_command = (
                f"timeout {timeout_secs} sh -c {quoted_cmd} 2>&1; "
                f"_RC=$?; echo ''; echo '{marker}:'$_RC"
            )
        elif self._timeout_mode == "perl":
            full_command = (
                f"perl -e 'alarm shift; exec @ARGV' {timeout_secs}"
                f" sh -c {quoted_cmd} 2>&1; "
                f"_RC=$?; echo ''; echo '{marker}:'$_RC"
            )
        else:
            full_command = (
                f"sh -c {quoted_cmd} 2>&1 & _CPID=$!; "
                f"( sleep {timeout_secs}; kill -9 $_CPID 2>/dev/null ) & "
                f"_WPID=$!; "
                f"wait $_CPID 2>/dev/null; _RC=$?; "
                f"kill $_WPID 2>/dev/null; wait $_WPID 2>/dev/null; "
                f"echo ''; echo '{marker}:'$_RC"
            )

        write_result = await shell_proc.stdio_write(full_command, with_enter=True)
        if not write_result.success:
            return 1, "", f"写入命令失败: {write_result.error}"

        output_lines: list[str] = []
        buffer = ""
        result_line: str | None = None

        while result_line is None:
            read_result = await shell_proc.stdio_read(wait_seconds=1.0)
            if not read_result.success:
                break
            decoded = read_result.stdout.decode(self._encoding, errors="replace")
            buffer += decoded
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip()
                if line.startswith(f"{marker}:"):
                    result_line = line
                    break
                output_lines.append(line)

        if result_line is None:
            return 1, "\n".join(output_lines), "无法获取命令返回码"

        parts = result_line.split(":", 1)
        if len(parts) == 2 and parts[1].strip().isdigit():
            exit_code = int(parts[1].strip())
        else:
            exit_code = 1

        return exit_code, "\n".join(output_lines), ""

    async def ping(self) -> ToolResultSuccess | ToolResultFailed:
        rc, stdout, stderr = await self.execute_raw("echo pong", timeout=5.0)
        if rc == 0 and "pong" in stdout:
            return ToolResultSuccess(content="pong")
        return ToolResultFailed(
            content=f"ping失败: rc={rc}, stdout={stdout}, stderr={stderr}"
        )

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpMessage | ToolResultFailed:
        raise NotImplementedError("http_request尚未在bash控制中实现")

    async def change_directory(
        self, directory: str
    ) -> ToolResultSuccess | ToolResultFailed:
        raise NotImplementedError("change_directory尚未在bash控制中实现")

    async def create_process(
        self, argv: list[str], wait_second: Optional[float] = None, pty: bool = False
    ) -> ProcessCreateResult:
        if pty:
            raise RuntimeError("BashHost不支持pty模式")
        self._counter += 1
        proc_id = str(self._counter)
        proc_dir = f"{self._tmp_dir}/proc_{proc_id}"

        cmd_str = shlex.join(argv)
        stdout_path = shlex.quote(f"{proc_dir}/stdout")
        stderr_path = shlex.quote(f"{proc_dir}/stderr")
        rc_path = shlex.quote(f"{proc_dir}/rc")

        setup_cmd = f"mkdir -p {shlex.quote(proc_dir)}"
        rc, _, stderr = await self.execute_raw(setup_cmd)
        if rc != 0:
            return ProcessCreateResult(
                pid="", success=False, error=f"创建进程目录失败: {stderr}"
            )

        start_cmd = (
            f"({cmd_str} < /dev/null > {stdout_path}"
            f" 2> {stderr_path};"
            f" echo $? > {rc_path}) & "
            f"echo $!"
        )
        rc, stdout, stderr = await self.execute_raw(start_cmd)
        if rc != 0:
            return ProcessCreateResult(
                pid="", success=False, error=f"启动进程失败: {stderr}"
            )

        pid = stdout.strip()
        if not pid or not pid.isdigit():
            return ProcessCreateResult(
                pid="", success=False, error=f"无法解析进程ID: {stdout}"
            )

        proc = BashProcess(pid=pid, proc_dir=proc_dir, host=self)
        self._processes[pid] = proc
        await self._notify_process_created(pid, argv)

        effective_wait = wait_second if wait_second is not None else 1.0
        if effective_wait > 0:
            await asyncio.sleep(effective_wait)
            check_cmd = f"test -f {rc_path} && cat {rc_path} || echo NONE"
            _, rc_str, _ = await self.execute_raw(check_cmd, timeout=5.0)
            if rc_str.strip() != "NONE":
                returncode = int(rc_str.strip()) if rc_str.strip().isdigit() else -1
                _, stdout_out, _ = await self.execute_raw(
                    f"cat {stdout_path} 2>/dev/null", timeout=5.0
                )
                _, stderr_out, _ = await self.execute_raw(
                    f"cat {stderr_path} 2>/dev/null", timeout=5.0
                )
                return ProcessCreateResult(
                    pid=pid,
                    success=True,
                    returncode=returncode,
                    stdout=stdout_out,
                    stderr=stderr_out,
                )

        return ProcessCreateResult(pid=pid, success=True, returncode=None)

    async def _notify_process_created(self, pid: str, argv: list[str]) -> None:
        if "lifecycle" not in self.registry.members:
            return
        from linhai.agent.lifecycle import Lifecycle

        process = self.get_process(pid)
        if process is None:
            return
        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        await lifecycle.after_process_create.trigger(
            ProcessCreateInfo(
                process=process,
                argv=argv,
                machine_id=self._machine_id,
            )
        )

    def get_process(self, pid: str) -> Process | None:
        return self._processes.get(pid)

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.terminal_create(self, columns, lines)

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.terminal_send_keys(self, terminal_id, keys)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.terminal_send_string(
            self, terminal_id, string, with_enter, wait_seconds
        )

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.terminal_read_screen(self, terminal_id)

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.terminal_close(self, terminal_id)

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> ToolResultSuccess | ToolResultFailed | FileContentMessage:
        return await _read_file(self, filepath, show_line_numbers)

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _write_file(self, filepath, content, override)

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _replace_file_content(self, filepath, old, new, replace_times)

    async def list_files(self, dirpath: str) -> ToolResultSuccess | ToolResultFailed:
        return await _list_files(self, dirpath)

    async def get_absolute_path(
        self, path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _get_absolute_path(self, path)

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        return await _read_file_with_sed(self, expression, filepath)

    async def get_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        return await _terminal.get_terminals(self, self._machine_id)

    def list_process_pids(self) -> list[str]:
        return list(self._processes.keys())

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        raise NotImplementedError("download_file_concurrent尚未在bash控制中实现")

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        raise NotImplementedError("upload_file_concurrent尚未在bash控制中实现")

    async def disconnect(self) -> None:
        if self._shell_process is not None:
            await self._shell_process.kill(graceful=True)
