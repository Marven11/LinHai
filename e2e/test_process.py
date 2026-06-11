import asyncio

import pytest

pytestmark = pytest.mark.asyncio

from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.machine_control.process import (
    ProcessReadResult,
    ProcessWaitResult,
    ProcessKillResult,
)
from linhai.registry import Registry
from linhai.sandbox import NoSandbox


def _create_host() -> MasterHostControl:
    registry = Registry()
    registry.register_member("process_sandbox", NoSandbox())
    return MasterHostControl(registry)


async def test_create_short_lived_process():
    host = _create_host()
    result = await host.create_process(["echo", "hello world"])
    assert result.success
    assert result.returncode == 0
    assert "hello world" in result.stdout


async def test_create_process_with_stderr():
    host = _create_host()
    result = await host.create_process(
        ["bash", "-c", "echo stdout_msg; echo stderr_msg >&2"]
    )
    assert result.success
    assert result.returncode == 0
    assert "stdout_msg" in result.stdout
    assert "stderr_msg" in result.stderr


async def test_create_process_nonzero_exit():
    host = _create_host()
    result = await host.create_process(["bash", "-c", "exit 42"])
    assert result.success
    assert result.returncode == 42


async def test_create_process_timeout():
    host = _create_host()
    result = await host.create_process(["sleep", "10"], wait_second=1.0)
    assert result.success
    assert result.returncode is None
    proc = host.get_process(result.pid)
    assert proc is not None
    kill_result = await proc.kill()
    assert isinstance(kill_result, ProcessKillResult)
    assert kill_result.success


async def test_interactive_bash_write_and_read():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    pid = result.pid

    proc = host.get_process(pid)
    assert proc is not None

    await proc.stdio_write("echo hello_from_bash", with_enter=True)
    await asyncio.sleep(0.5)
    read_result = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"hello_from_bash" in read_result.stdout

    await proc.kill()


async def test_interactive_bash_multiple_commands():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    await proc.stdio_write("echo cmd1", with_enter=True)
    await asyncio.sleep(0.5)
    read1 = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read1, ProcessReadResult)
    assert read1.success
    assert b"cmd1" in read1.stdout

    await proc.stdio_write("echo cmd2", with_enter=True)
    await asyncio.sleep(0.5)
    read2 = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read2, ProcessReadResult)
    assert read2.success
    assert b"cmd2" in read2.stdout

    await proc.stdio_write("echo cmd3", with_enter=True)
    await asyncio.sleep(0.5)
    read3 = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read3, ProcessReadResult)
    assert read3.success
    assert b"cmd3" in read3.stdout

    await proc.kill()


async def test_interactive_bash_nonblocking_read():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    read_empty = await proc.stdio_read(wait_seconds=1.0)
    assert isinstance(read_empty, ProcessReadResult)
    assert read_empty.success

    await proc.stdio_write("echo after_empty_read", with_enter=True)
    await asyncio.sleep(0.5)
    read_after = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read_after, ProcessReadResult)
    assert read_after.success
    assert b"after_empty_read" in read_after.stdout

    await proc.kill()


async def test_interactive_bash_stderr():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    await proc.stdio_write("echo err_msg >&2", with_enter=True)
    await asyncio.sleep(0.5)
    read_result = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"err_msg" in read_result.stderr

    await proc.kill()


async def test_interactive_bash_with_variables():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    await proc.stdio_write("MY_VAR=hello123", with_enter=True)
    await asyncio.sleep(0.3)
    await proc.stdio_write("echo $MY_VAR", with_enter=True)
    await asyncio.sleep(0.5)
    read_result = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"hello123" in read_result.stdout

    await proc.kill()


async def test_wait_for_process():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    await proc.stdio_write("echo wait_test; exit 0", with_enter=True)
    wait_result = await proc.wait(timeout=5.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode == 0
    assert "wait_test" in wait_result.stdout


async def test_kill_process():
    host = _create_host()
    result = await host.create_process(["sleep", "100"], wait_second=1.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    kill_result = await proc.kill(graceful=False)
    assert isinstance(kill_result, ProcessKillResult)
    assert kill_result.success

    await asyncio.sleep(0.5)
    wait_result = await proc.wait(timeout=2.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode is not None
    assert wait_result.returncode != 0


async def test_get_process_unknown_pid():
    host = _create_host()
    assert host.get_process("nonexistent_pid") is None


async def test_stdio_read_then_wait_captures_remaining_output():
    host = _create_host()
    result = await host.create_process(
        [
            "python3",
            "-c",
            "import sys,time;sys.stdout.write('hello\\n');sys.stdout.flush();"
            "time.sleep(1);sys.stdout.write('world\\n');sys.stdout.flush()",
        ],
        wait_second=0.3,
    )
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    read_result = await proc.stdio_read(wait_seconds=0.3)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"hello" in read_result.stdout
    assert b"world" not in read_result.stdout

    wait_result = await proc.wait(timeout=10.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode == 0
    assert "world" in wait_result.stdout


async def test_stdio_read_then_wait_tight_timing():
    host = _create_host()
    result = await host.create_process(
        [
            "python3",
            "-c",
            "import sys,time;sys.stdout.write('hello\\n');sys.stdout.flush();"
            "time.sleep(0.3);sys.stdout.write('world\\n');sys.stdout.flush()",
        ],
        wait_second=0.1,
    )
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    read_result = await proc.stdio_read(wait_seconds=0.1)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success

    wait_result = await proc.wait(timeout=10.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode == 0

    total_output = (read_result.stdout or b"") + wait_result.stdout.encode()
    assert (
        b"hello" in total_output
    ), f"read={read_result.stdout!r} wait={wait_result.stdout!r}"
    assert (
        b"world" in total_output
    ), f"read={read_result.stdout!r} wait={wait_result.stdout!r}"


async def test_stdio_read_then_wait_large_output():
    host = _create_host()
    result = await host.create_process(
        [
            "python3",
            "-c",
            "import sys,time;sys.stdout.write('hello\\n');sys.stdout.flush();"
            "time.sleep(1);sys.stdout.write('x'*2000000);sys.stdout.flush()",
        ],
        wait_second=0.5,
    )
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    read_result = await proc.stdio_read(wait_seconds=0.5)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"hello" in read_result.stdout

    wait_result = await proc.wait(timeout=30.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode == 0

    total_x = read_result.stdout.count(b"x") + wait_result.stdout.count("x")
    assert total_x == 2000000, f"Expected 2000000 x's, got {total_x}"


async def test_stdio_read_exit_note_when_process_exits():
    host = _create_host()
    result = await host.create_process(
        [
            "python3",
            "-c",
            "import sys,time;sys.stdout.write('hello\\n');sys.stdout.flush();"
            "time.sleep(0.3);sys.stdout.write('world\\n');sys.stdout.flush()",
        ],
        wait_second=0.1,
    )
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    read_result = await proc.stdio_read(wait_seconds=1.0)
    assert isinstance(read_result, ProcessReadResult)
    assert read_result.success
    assert b"hello" in read_result.stdout
    assert b"world" in read_result.stdout
    assert read_result.exit_note is not None
    assert "已经退出" in read_result.exit_note

    wait_result = await proc.wait(timeout=5.0)
    assert isinstance(wait_result, ProcessWaitResult)
    assert wait_result.success
    assert wait_result.returncode == 0


async def test_stdio_write_without_enter():
    host = _create_host()
    result = await host.create_process(["/usr/bin/env", "bash"], wait_second=2.0)
    assert result.success
    proc = host.get_process(result.pid)
    assert proc is not None

    await proc.stdio_write("echo hello", with_enter=False)
    await asyncio.sleep(0.3)
    read_before = await proc.stdio_read(wait_seconds=1.0)
    assert isinstance(read_before, ProcessReadResult)
    assert read_before.success

    await proc.stdio_write("", with_enter=True)
    await asyncio.sleep(0.5)
    read_after = await proc.stdio_read(wait_seconds=2.0)
    assert isinstance(read_after, ProcessReadResult)
    assert read_after.success
    assert b"hello" in read_after.stdout

    await proc.kill()
