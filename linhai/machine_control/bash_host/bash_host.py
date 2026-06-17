"""BashHostControl: 通过raw bash命令控制远程机器。"""

import asyncio
import base64
import pathlib
import shlex
import uuid
from typing import Any, Dict, Optional, Union

from rich.text import Text

from linhai.tool.base import (
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
)
from linhai.machine_control.http_message import HttpToolResult
from linhai.machine_control.process import (
    ProcessIOError,
    Process,
    ProcessCreateResult,
)
from linhai.registry import Registry
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
from .http import http_request as _http_request


def _strip_ansi_and_cr(text: str) -> str:
    return Text.from_ansi(text).plain.replace("\r", "")


def _split_marker_for_echo(marker: str) -> str:
    mid = len(marker) // 2
    return marker[:mid] + '""' + marker[mid:]


class BashHostControl:
    """通过raw bash命令控制远程机器，不依赖远程Python环境。"""

    GLOBAL_TIMEOUT = 30.0

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self._machine_id: str = ""
        self._shell_process: Optional[Process] = None
        self._tmp_dir: str = ""
        self._encoding: str = "utf-8"
        self._counter: int = 0
        self._timeout_mode: str = "builtin"
        self._processes: dict[str, BashProcess] = {}
        self._cwd: str = ""
        self._has_curl: bool = False
        self._execute_lock = asyncio.Lock()

    def make_temp_path(self, prefix: str) -> str:
        self._counter += 1
        return f"{self._tmp_dir}/{prefix}_{self._counter}"

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

        rc, stdout, _ = await self.execute_raw("pwd")
        if rc == 0:
            self._cwd = stdout.strip()

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

        rc, _, _ = await self.execute_raw("command -v curl >/dev/null 2>&1")
        self._has_curl = rc == 0

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"Bash控制连接成功 (编码: {self._encoding}, timeout: {self._timeout_mode}, curl: {self._has_curl}, 临时目录: {self._tmp_dir})",
            ),
        )
        return True

    async def execute_raw(
        self, command: str, timeout: float = 0.0
    ) -> tuple[int, str, str]:
        if self._shell_process is None:
            return 1, "", "未建立连接"

        async with self._execute_lock:
            shell_proc = self._shell_process
            effective_timeout = timeout if timeout > 0 else self.GLOBAL_TIMEOUT
            marker_hex = uuid.uuid4().hex[:8]
            marker_open = f"<linhai_{marker_hex}>"
            marker_close = f"</linhai_{marker_hex}>"

            marker_open_echo = _split_marker_for_echo(marker_open)
            marker_close_echo = _split_marker_for_echo(marker_close)

            quoted_cmd = shlex.quote(command)

            timeout_secs = int(effective_timeout)
            if self._timeout_mode == "timeout":
                full_command = (
                    f'echo "{marker_open_echo}"; '
                    f"timeout {timeout_secs} sh -c {quoted_cmd} 2>&1; "
                    f'RC=$?; echo "${{RC}}{marker_close_echo}"'
                )
            elif self._timeout_mode == "perl":
                full_command = (
                    f'echo "{marker_open_echo}"; '
                    f"perl -e 'alarm shift; exec @ARGV' {timeout_secs}"
                    f" sh -c {quoted_cmd} 2>&1; "
                    f'RC=$?; echo "${{RC}}{marker_close_echo}"'
                )
            else:
                full_command = (
                    f'echo "{marker_open_echo}"; '
                    f"sh -c {quoted_cmd} 2>&1 & _CPID=$!; "
                    f"( sleep {timeout_secs}; kill -9 $_CPID 2>/dev/null ) & "
                    f"_WPID=$!; "
                    f"wait $_CPID 2>/dev/null; RC=$?; "
                    f"kill $_WPID 2>/dev/null; wait $_WPID 2>/dev/null; "
                    f'echo "${{RC}}{marker_close_echo}"'
                )

            write_result = await shell_proc.stdio_write(full_command, with_enter=True)
            if isinstance(write_result, ProcessIOError):
                return 1, "", f"IO错误: {write_result.error}"
            if not write_result.success:
                return 1, "", f"写入命令失败: {write_result.error}"

            buffer = ""
            start_time = asyncio.get_event_loop().time()

            while asyncio.get_event_loop().time() - start_time < effective_timeout:
                read_result = await shell_proc.stdio_read(wait_seconds=1.0)
                if isinstance(read_result, ProcessIOError):
                    break
                if not read_result.success:
                    break
                decoded = read_result.stdout.decode(self._encoding, errors="replace")
                buffer += _strip_ansi_and_cr(decoded)

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

    async def ping(self) -> SuccessfulToolResult | FailedToolResult:
        rc, stdout, stderr = await self.execute_raw("echo pong", timeout=5.0)
        if rc == 0 and "pong" in stdout:
            return SuccessfulToolResult(content="pong")
        return FailedToolResult(
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
    ) -> HttpToolResult | FailedToolResult:
        if not self._has_curl:
            return FailedToolResult(content="远程机器没有安装curl")
        return await _http_request(
            self,
            method,
            url,
            params,
            headers,
            data,
            follow_redirects,
            timeout,
            auth,
            cookies,
            json_data,
            proxy,
            verify,
        )

    async def change_directory(
        self, directory: str
    ) -> SuccessfulToolResult | FailedToolResult:
        rc, stdout, stderr = await self.execute_raw(
            f"cd {shlex.quote(directory)} 2>&1 && pwd"
        )
        if rc != 0:
            return FailedToolResult(content=f"切换目录失败: {stderr or stdout}")
        old_cwd = self._cwd
        self._cwd = stdout.strip().split("\n")[-1].strip()
        return SuccessfulToolResult(content=f"从目录{old_cwd}切换到了{self._cwd}")

    async def create_process(
        self,
        argv: list[str],
        wait_second: Optional[float] = None,
        override_env: Optional[Dict[str, str]] = None,
    ) -> ProcessCreateResult:
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

        env_prefix = ""
        if override_env is not None:
            env_prefix = (
                " ".join(
                    f"{shlex.quote(k)}={shlex.quote(v)}"
                    for k, v in override_env.items()
                )
                + " "
            )

        start_cmd = (
            f"(cd {shlex.quote(self._cwd)} && {env_prefix}{cmd_str} < /dev/null"
            f" > {stdout_path} 2> {stderr_path};"
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

    def get_process(self, pid: str) -> Process | None:
        return self._processes.get(pid)

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.terminal_create(self, columns, lines)

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.terminal_send_keys(self, terminal_id, keys)

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.terminal_send_string(
            self, terminal_id, string, with_enter, wait_seconds
        )

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.terminal_read_screen(self, terminal_id)

    async def terminal_close(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.terminal_close(self, terminal_id)

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> SuccessfulToolResult | FailedToolResult | FileContentToolResult:
        return await _read_file(self, filepath, show_line_numbers)

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _write_file(self, filepath, content, override)

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _replace_file_content(self, filepath, old, new, replace_times)

    async def list_files(self, dirpath: str) -> SuccessfulToolResult | FailedToolResult:
        return await _list_files(self, dirpath)

    async def list_files_glob(
        self, pattern: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="list_files_glob仅支持master_host")

    async def get_absolute_path(
        self, path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _get_absolute_path(self, path)

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await _read_file_with_sed(self, expression, filepath)

    async def get_terminals(self) -> SuccessfulToolResult | FailedToolResult:
        return await _terminal.get_terminals(self, self._machine_id)

    def list_process_pids(self) -> list[str]:
        return list(self._processes.keys())

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        rc, _, _ = await self.execute_raw(f"test -f {shlex.quote(remote_path)}")
        if rc != 0:
            return FailedToolResult(content=f"远程文件不存在: {remote_path}")

        rc, size_str, _ = await self.execute_raw(f"wc -c < {shlex.quote(remote_path)}")
        if rc != 0 or not size_str.strip().isdigit():
            return FailedToolResult(content=f"无法获取文件大小: {remote_path}")

        file_size = int(size_str.strip())
        chunk_size = 30720
        data = bytearray()

        for offset in range(0, file_size, chunk_size):
            cmd = (
                f"dd if={shlex.quote(remote_path)} bs={chunk_size}"
                f" skip={offset // chunk_size} count=1 2>/dev/null | base64"
            )
            rc, b64_data, _ = await self.execute_raw(cmd, timeout=60.0)
            if rc != 0:
                return FailedToolResult(content=f"读取文件块失败 (offset={offset})")
            if b64_data.strip():
                data.extend(base64.b64decode(b64_data.strip()))

        pathlib.Path(local_path).write_bytes(bytes(data))
        return SuccessfulToolResult(
            content=f"文件已下载: {local_path} ({file_size}字节)"
        )

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        parent = remote_path.rsplit("/", 1)[0] if "/" in remote_path else "."
        rc, _, _ = await self.execute_raw(f"test -d {shlex.quote(parent)}")
        if rc != 0:
            return FailedToolResult(content=f"远程目录不存在: {parent}")

        chunk_size = 30720
        tmp_path = self.make_temp_path("upload")

        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            encoded = base64.b64encode(chunk).decode("ascii")
            redirect = ">" if i == 0 else ">>"
            cmd = f"echo '{encoded}' | base64 -d {redirect} {shlex.quote(tmp_path)}"
            rc, _, stderr = await self.execute_raw(cmd, timeout=30.0)
            if rc != 0:
                await self.execute_raw(f"rm -f {shlex.quote(tmp_path)}")
                return FailedToolResult(content=f"上传文件块失败: {stderr}")

        rc, _, stderr = await self.execute_raw(
            f"mv {shlex.quote(tmp_path)} {shlex.quote(remote_path)}"
        )
        if rc != 0:
            await self.execute_raw(f"rm -f {shlex.quote(tmp_path)}")
            return FailedToolResult(content=f"移动文件失败: {stderr}")

        return SuccessfulToolResult(
            content=f"文件已上传: {remote_path} ({len(data)}字节)"
        )

    async def disconnect(self) -> None:
        if self._shell_process is not None:
            await self._shell_process.kill(graceful=True)
