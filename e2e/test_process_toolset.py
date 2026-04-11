import asyncio
import json

import pytest

pytestmark = pytest.mark.asyncio

from linhai.machine_control.main import MachineControl, register_machine_control_tools
from linhai.registry import Registry
from linhai.sandbox import NoSandbox
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


def _create_toolset():
    registry = Registry()
    registry.register_member("process_sandbox", NoSandbox())
    mc = MachineControl(registry, tmux_terminal=False)
    toolset = register_machine_control_tools(mc)
    return mc, toolset


def _tool_ok(result) -> str:
    assert isinstance(result, ToolResultSuccess)
    return result.content


def _tool_fail(result) -> str:
    assert isinstance(result, ToolResultFailed)
    return result.content


def _extract_pid(content: str) -> str:
    start = content.index("<<pid>>") + len("<<pid>>")
    end = content.index("<<pid>>", start)
    return content[start:end]


async def test_tool_process_create_and_read():
    mc, ts = _create_toolset()
    result = await ts.call_tool("process_create", {"argv": ["echo", "hello toolset"]})
    content = _tool_ok(result)
    assert "hello toolset" in content
    assert "<<pid>>" in content
    assert "<<returncode>>0<<returncode>>" in content


async def test_tool_process_create_with_stderr():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_create",
        {"argv": ["bash", "-c", "echo out_msg; echo err_msg >&2"]},
    )
    content = _tool_ok(result)
    assert "out_msg" in content
    assert "err_msg" in content
    assert "<<returncode>>0<<returncode>>" in content


async def test_tool_process_create_nonzero_exit():
    mc, ts = _create_toolset()
    result = await ts.call_tool("process_create", {"argv": ["bash", "-c", "exit 42"]})
    content = _tool_ok(result)
    assert "<<returncode>>42<<returncode>>" in content


async def test_tool_interactive_bash_lifecycle():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_create",
        {"argv": ["/usr/bin/env", "bash"], "wait_second": 2.0},
    )
    content = _tool_ok(result)
    assert "<<pid>>" in content
    assert "<<message>>" in content
    pid = _extract_pid(content)

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo first_cmd", "with_enter": True},
    )
    await asyncio.sleep(0.5)

    read_result = await ts.call_tool("process_stdio_read", {"pid": pid, "timeout": 2.0})
    read_content = _tool_ok(read_result)
    read_data = json.loads(read_content)
    assert read_data["success"] is True
    assert "first_cmd" in read_data["stdout"]

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo second_cmd", "with_enter": True},
    )
    await asyncio.sleep(0.5)

    read_result2 = await ts.call_tool(
        "process_stdio_read", {"pid": pid, "timeout": 2.0}
    )
    read_content2 = _tool_ok(read_result2)
    read_data2 = json.loads(read_content2)
    assert "second_cmd" in read_data2["stdout"]

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "MY_VAR=toolset_test", "with_enter": True},
    )
    await asyncio.sleep(0.3)
    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo $MY_VAR", "with_enter": True},
    )
    await asyncio.sleep(0.5)

    read_result3 = await ts.call_tool(
        "process_stdio_read", {"pid": pid, "timeout": 2.0}
    )
    read_content3 = _tool_ok(read_result3)
    read_data3 = json.loads(read_content3)
    assert "toolset_test" in read_data3["stdout"]

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo done; exit 0", "with_enter": True},
    )

    wait_result = await ts.call_tool("process_wait", {"pid": pid, "timeout": 5.0})
    wait_content = _tool_ok(wait_result)
    assert "<<returncode>>0<<returncode>>" in wait_content
    assert "done" in wait_content


async def test_tool_process_kill():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_create", {"argv": ["sleep", "100"], "wait_second": 1.0}
    )
    content = _tool_ok(result)
    pid = _extract_pid(content)

    kill_result = await ts.call_tool("process_kill", {"pid": pid, "graceful": False})
    _tool_ok(kill_result)

    await asyncio.sleep(0.5)
    wait_result = await ts.call_tool("process_wait", {"pid": pid, "timeout": 2.0})
    err = _tool_fail(wait_result)
    assert "进程不存在" in err


async def test_tool_nonexistent_process():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_stdio_write",
        {"pid": "fake_pid", "content": "test", "with_enter": True},
    )
    err = _tool_fail(result)
    assert "进程不存在" in err

    result2 = await ts.call_tool(
        "process_stdio_read", {"pid": "fake_pid", "timeout": 1.0}
    )
    err2 = _tool_fail(result2)
    assert "进程不存在" in err2

    result3 = await ts.call_tool("process_wait", {"pid": "fake_pid", "timeout": 1.0})
    err3 = _tool_fail(result3)
    assert "进程不存在" in err3

    result4 = await ts.call_tool("process_kill", {"pid": "fake_pid"})
    err4 = _tool_fail(result4)
    assert "进程不存在" in err4


async def test_tool_stderr_in_read():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_create",
        {"argv": ["/usr/bin/env", "bash"], "wait_second": 2.0},
    )
    content = _tool_ok(result)
    pid = _extract_pid(content)

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo stderr_line >&2", "with_enter": True},
    )
    await asyncio.sleep(0.5)

    read_result = await ts.call_tool("process_stdio_read", {"pid": pid, "timeout": 2.0})
    read_content = _tool_ok(read_result)
    read_data = json.loads(read_content)
    assert "stderr_line" in read_data["stderr"]

    await ts.call_tool("process_kill", {"pid": pid, "graceful": False})


async def test_tool_nonblocking_read():
    mc, ts = _create_toolset()
    result = await ts.call_tool(
        "process_create",
        {"argv": ["/usr/bin/env", "bash"], "wait_second": 2.0},
    )
    content = _tool_ok(result)
    pid = _extract_pid(content)

    read_empty = await ts.call_tool("process_stdio_read", {"pid": pid, "timeout": 1.0})
    read_empty_content = _tool_ok(read_empty)
    read_empty_data = json.loads(read_empty_content)
    assert read_empty_data["success"] is True

    await ts.call_tool(
        "process_stdio_write",
        {"pid": pid, "content": "echo after_empty", "with_enter": True},
    )
    await asyncio.sleep(0.5)

    read_after = await ts.call_tool("process_stdio_read", {"pid": pid, "timeout": 2.0})
    read_after_content = _tool_ok(read_after)
    read_after_data = json.loads(read_after_content)
    assert "after_empty" in read_after_data["stdout"]

    await ts.call_tool("process_kill", {"pid": pid, "graceful": False})
