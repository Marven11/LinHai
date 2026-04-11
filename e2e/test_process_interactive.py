import asyncio
import json

from linhai.machine_control.process import LocalProcess
from linhai.tool.base import ToolResultSuccess


async def _create_bash_process() -> LocalProcess:
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/env",
        "bash",
        "-i",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return LocalProcess(str(proc.pid), proc)


async def test_process_create_and_read():
    p = await _create_bash_process()
    assert p.returncode is None
    await p.kill()


async def test_process_write_echo_and_read_nonblocking():
    p = await _create_bash_process()
    await p.stdio_write("echo hello_from_bash", with_enter=True)
    await asyncio.sleep(0.3)
    result = await p.stdio_read(timeout=1.0)
    assert isinstance(result, ToolResultSuccess)
    data = json.loads(result.content)
    assert data["success"] is True
    combined = data["stdout"] + data["stderr"]
    assert "hello_from_bash" in combined
    await p.kill()


async def test_process_multiple_interactions():
    p = await _create_bash_process()
    await p.stdio_write("echo first_cmd", with_enter=True)
    await asyncio.sleep(0.3)
    r1 = await p.stdio_read(timeout=1.0)
    assert isinstance(r1, ToolResultSuccess)
    d1 = json.loads(r1.content)
    assert "first_cmd" in d1["stdout"] + d1["stderr"]

    await p.stdio_write("echo second_cmd", with_enter=True)
    await asyncio.sleep(0.3)
    r2 = await p.stdio_read(timeout=1.0)
    assert isinstance(r2, ToolResultSuccess)
    d2 = json.loads(r2.content)
    assert "second_cmd" in d2["stdout"] + d2["stderr"]

    await p.kill()


async def test_process_read_empty_buffer_no_block():
    p = await _create_bash_process()
    result = await p.stdio_read(timeout=0.2)
    assert isinstance(result, ToolResultSuccess)
    data = json.loads(result.content)
    assert data["success"] is True
    await p.kill()


async def test_process_wait_exits_on_command():
    p = await _create_bash_process()
    await p.stdio_write("exit 42", with_enter=True)
    result = await p.wait(timeout=3.0)
    assert isinstance(result, ToolResultSuccess)
    assert "42" in result.content
    assert p.returncode == 42


async def test_process_kill_terminates():
    p = await _create_bash_process()
    result = await p.kill(graceful=True)
    assert isinstance(result, ToolResultSuccess)
    assert p.returncode is not None
