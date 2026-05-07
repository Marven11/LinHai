from __future__ import annotations

import asyncio
import base64
import shlex
from typing import TYPE_CHECKING

from linhai.machine_control.process import (
    ProcessIOError,
    ProcessKillResult,
    ProcessReadResult,
    ProcessWaitResult,
    ProcessWriteResult,
)

if TYPE_CHECKING:
    from .bash_host import BashHostControl


class BashProcess:
    def __init__(self, pid: str, proc_dir: str, host: BashHostControl) -> None:
        self._pid = pid
        self._proc_dir = proc_dir
        self._host = host
        self._stdout_offset: int = 0
        self._stderr_offset: int = 0

    @property
    def pid(self) -> str:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return None

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ProcessWriteResult | ProcessIOError:
        text = content + ("\n" if with_enter else "")
        stdin_path = shlex.quote(f"{self._proc_dir}/stdin")
        cmd = f"printf '%s' {shlex.quote(text)} >> {stdin_path}"
        rc, _, stderr = await self._host.execute_raw(cmd, timeout=5.0)
        if rc != 0:
            return ProcessWriteResult(pid=self._pid, success=False, error=stderr)
        return ProcessWriteResult(pid=self._pid, success=True)

    async def stdio_read(
        self, wait_seconds: float
    ) -> ProcessReadResult | ProcessIOError:
        stdout_path = shlex.quote(f"{self._proc_dir}/stdout")
        stderr_path = shlex.quote(f"{self._proc_dir}/stderr")

        out_cmd = (
            f"tail -c +{self._stdout_offset + 1} {stdout_path}" " 2>/dev/null | base64"
        )
        _, out_b64, _ = await self._host.execute_raw(out_cmd, timeout=wait_seconds + 2)
        stdout_data = base64.b64decode(out_b64.strip()) if out_b64.strip() else b""

        size_cmd = f"wc -c < {stdout_path} 2>/dev/null || echo 0"
        _, size_str, _ = await self._host.execute_raw(size_cmd, timeout=5.0)
        if size_str.strip().isdigit():
            self._stdout_offset = int(size_str.strip())

        err_cmd = (
            f"tail -c +{self._stderr_offset + 1} {stderr_path}" " 2>/dev/null | base64"
        )
        _, err_b64, _ = await self._host.execute_raw(err_cmd, timeout=wait_seconds + 2)
        stderr_data = base64.b64decode(err_b64.strip()) if err_b64.strip() else b""

        size_cmd = f"wc -c < {stderr_path} 2>/dev/null || echo 0"
        _, size_str, _ = await self._host.execute_raw(size_cmd, timeout=5.0)
        if size_str.strip().isdigit():
            self._stderr_offset = int(size_str.strip())

        return ProcessReadResult(
            pid=self._pid,
            success=True,
            stdout=stdout_data,
            stderr=stderr_data,
        )

    async def wait(self, timeout: float) -> ProcessWaitResult | ProcessIOError:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        rc_path = shlex.quote(f"{self._proc_dir}/rc")
        stdout_path = shlex.quote(f"{self._proc_dir}/stdout")
        stderr_path = shlex.quote(f"{self._proc_dir}/stderr")

        while True:
            rc_cmd = f"test -f {rc_path} && cat {rc_path} || echo NONE"
            _, rc_str, _ = await self._host.execute_raw(rc_cmd, timeout=5.0)
            if rc_str.strip() != "NONE":
                returncode = int(rc_str.strip()) if rc_str.strip().isdigit() else -1
                _, stdout_out, _ = await self._host.execute_raw(
                    f"cat {stdout_path} 2>/dev/null", timeout=5.0
                )
                _, stderr_out, _ = await self._host.execute_raw(
                    f"cat {stderr_path} 2>/dev/null", timeout=5.0
                )
                return ProcessWaitResult(
                    pid=self._pid,
                    success=True,
                    returncode=returncode,
                    stdout=stdout_out,
                    stderr=stderr_out,
                )

            if loop.time() >= deadline:
                return ProcessWaitResult(
                    pid=self._pid,
                    success=False,
                    error="等待超时",
                )

            await asyncio.sleep(0.5)

    def _is_alive_cmd(self) -> str:
        return (
            f"if kill -0 {self._pid} 2>/dev/null; then "
            f"if grep -qs '^State:.*Z' /proc/{self._pid}/status 2>/dev/null; then "
            f"echo DEAD; else echo ALIVE; fi; else echo DEAD; fi"
        )

    async def kill(self, graceful: bool = True) -> ProcessKillResult | ProcessIOError:
        sig = "TERM" if graceful else "9"
        cmd = (
            f"kill -{sig} {self._pid} 2>/dev/null"
            f"; pkill -{sig} -P {self._pid} 2>/dev/null; true"
        )
        await self._host.execute_raw(cmd, timeout=5.0)
        for _ in range(5):
            _, status, _ = await self._host.execute_raw(self._is_alive_cmd())
            if "DEAD" in status:
                break
            await asyncio.sleep(0.5)
            await self._host.execute_raw(
                f"kill -9 {self._pid} 2>/dev/null; pkill -9 -P {self._pid} 2>/dev/null; true"
            )
        return ProcessKillResult(pid=self._pid, success=True, message="进程已终止")
