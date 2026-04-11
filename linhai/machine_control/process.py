import asyncio
import json
import re
import time
from typing import Optional, Protocol, Callable, runtime_checkable

from linhai.tool.base import ToolResultSuccess, ToolResultFailed

_MAX_READ_SIZE = 32 * 1024
_CHUNK_TIMEOUT = 0.1


@runtime_checkable
class Process(Protocol):
    pid: str

    @property
    def returncode(self) -> Optional[int]: ...

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def stdio_read(
        self, unescape_ansi: bool = True, timeout: float = 60.0
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def wait(self, timeout: float) -> ToolResultSuccess | ToolResultFailed: ...

    async def kill(
        self, graceful: bool = True
    ) -> ToolResultSuccess | ToolResultFailed: ...


class LocalProcess:
    def __init__(
        self,
        pid: str,
        process: asyncio.subprocess.Process,
        on_exit: Callable[["LocalProcess"], None] | None = None,
    ):
        self.pid = pid
        self._process = process
        self._on_exit = on_exit
        self._exit_notified = False

    @property
    def returncode(self) -> Optional[int]:
        return self._process.returncode

    def _check_exit(self) -> None:
        if not self._exit_notified and self._process.returncode is not None:
            self._exit_notified = True
            if self._on_exit is not None:
                self._on_exit(self)

    async def _read_available(
        self, stream: Optional[asyncio.StreamReader], timeout_seconds: float
    ) -> bytes:
        if stream is None:
            return b""

        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout_seconds

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            read_task = asyncio.ensure_future(stream.read(_MAX_READ_SIZE))
            sleep_task = asyncio.ensure_future(
                asyncio.sleep(min(remaining, _CHUNK_TIMEOUT))
            )

            done, pending = await asyncio.wait(
                [read_task, sleep_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for p in pending:
                p.cancel()

            if read_task in done:
                data = read_task.result()
                if not data:
                    break
                chunks.append(data)

        return b"".join(chunks)

    async def stdio_read(
        self, unescape_ansi: bool = True, timeout: float = 60.0
    ) -> ToolResultSuccess | ToolResultFailed:
        stdout_data, stderr_data = await asyncio.gather(
            self._read_available(self._process.stdout, timeout),
            self._read_available(self._process.stderr, timeout),
        )

        stdout_str = stdout_data.decode("utf-8", errors="replace")
        stderr_str = stderr_data.decode("utf-8", errors="replace")

        if unescape_ansi:
            ansi_escape = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
            stdout_str = ansi_escape.sub("", stdout_str)
            stderr_str = ansi_escape.sub("", stderr_str)

        exit_note = None
        if self._process.returncode is not None:
            exit_note = f"注意：当前程序{self.pid}已经退出\n"
            self._check_exit()

        return ToolResultSuccess(
            content=json.dumps(
                {
                    "pid": self.pid,
                    "success": True,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_note": exit_note,
                    "timestamp": time.time(),
                }
            )
        )

    async def stdio_write(
        self, content: str, with_enter: bool
    ) -> ToolResultSuccess | ToolResultFailed:
        process = self._process
        if process.stdin is None:
            return ToolResultFailed(content=f"进程 {self.pid} 没有标准输入")
        write_content = (content + "\n") if with_enter else content
        process.stdin.write(write_content.encode("utf-8"))
        await process.stdin.drain()
        return ToolResultSuccess(
            content=json.dumps(
                {
                    "pid": self.pid,
                    "success": True,
                    "message": "写入成功",
                    "timestamp": time.time(),
                }
            )
        )

    async def wait(self, timeout: float) -> ToolResultSuccess | ToolResultFailed:
        if timeout > 3600:
            return ToolResultFailed(content="超时时间不能超过3600秒")

        wait_task = asyncio.ensure_future(self._process.wait())
        sleep_task = asyncio.ensure_future(asyncio.sleep(timeout))

        done, pending = await asyncio.wait(
            [wait_task, sleep_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for p in pending:
            p.cancel()

        if wait_task not in done:
            return ToolResultFailed(content=f"等待进程 {self.pid} 超时")

        stdout_data = b""
        stderr_data = b""
        if self._process.stdout:
            stdout_data = await self._process.stdout.read()
        if self._process.stderr:
            stderr_data = await self._process.stderr.read()
        stdout_str = stdout_data.decode("utf-8", errors="replace")
        stderr_str = stderr_data.decode("utf-8", errors="replace")
        self._check_exit()
        return ToolResultSuccess(
            content=f"<<pid>>{self.pid}<<pid>><<returncode>>{self._process.returncode}<<returncode>><<stdout>>{stdout_str}<<stdout>><<stderr>>{stderr_str}<<stderr>>"
        )

    async def kill(self, graceful: bool = True) -> ToolResultSuccess | ToolResultFailed:
        process = self._process
        if graceful:
            process.terminate()
            wait_task = asyncio.ensure_future(process.wait())
            sleep_task = asyncio.ensure_future(asyncio.sleep(5.0))
            done, pending = await asyncio.wait(
                [wait_task, sleep_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
            if wait_task not in done:
                process.kill()
                await process.wait()
        else:
            process.kill()
            await process.wait()
        self._check_exit()
        return ToolResultSuccess(
            content=f"<<pid>>{self.pid}<<pid>><<message>>进程已终止<<message>>"
        )
