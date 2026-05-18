import asyncio
import os
import shutil

import pytest

from linhai.machine_control.main import _check_shell_compatibility
from linhai.machine_control.process import ProcessWriteResult, ProcessReadResult


@pytest.fixture(autouse=True)
def _assert_fish_installed():
    assert shutil.which("fish") is not None, "fish must be installed for e2e tests"


class _PipeProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def stdio_write(
        self, data: str, with_enter: bool = True
    ) -> ProcessWriteResult:
        if with_enter:
            data += "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()
        return ProcessWriteResult(
            pid=str(self._process.pid), success=True, message="ok"
        )

    async def stdio_read(self, timeout: float) -> ProcessReadResult:
        try:
            data = await asyncio.wait_for(
                self._process.stdout.read(4096), timeout=timeout
            )
        except asyncio.TimeoutError:
            data = b""
        return ProcessReadResult(
            pid=str(self._process.pid),
            success=True,
            stdout=data,
            stderr=b"",
            exit_note="",
        )

    async def kill(self) -> None:
        self._process.kill()
        await self._process.wait()


async def _start_bash_with_fish_shell_env() -> _PipeProcess:
    fish_path = shutil.which("fish")
    assert fish_path is not None
    env = {**os.environ, "SHELL": fish_path}
    process = await asyncio.create_subprocess_exec(
        "bash",
        "-i",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    await asyncio.sleep(0.5)
    assert process.returncode is None
    return _PipeProcess(process)


@pytest.mark.asyncio
async def test_bash_with_fish_login_shell_accepted() -> None:
    proc = await _start_bash_with_fish_shell_env()
    try:
        compatible, shell_name = await _check_shell_compatibility(proc)
        assert compatible
        assert shell_name == "bash"
    finally:
        await proc.kill()
