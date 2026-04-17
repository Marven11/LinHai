from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, Optional, Union, Any
from linhai.agent.messages import FileContentMessage
from linhai.machine_control.process import ProcessCreateInfo
from linhai.tool.base import (
    ToolArgInfo,
    ToolResultSuccess,
    ToolResultFailed,
    ToolSet,
)
from rich.text import Text

if TYPE_CHECKING:
    from .main import MachineControl


def register_machine_control_tools(machine_control: "MachineControl") -> ToolSet:
    """注册所有工具"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="list_terminals",
        desc="列出所有机器上的所有终端",
        args={},
        required_args=[],
    )
    async def list_terminals_tool() -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.list_all_terminals()

    @toolset.register_tool(
        name="list_machines",
        desc="列出所有可用的机器",
        args={},
        required_args=[],
    )
    async def list_machines_tool() -> ToolResultSuccess:
        return await machine_control.list_machines()

    @toolset.register_tool(
        name="switch_machine",
        desc="切换到指定机器",
        args={"machine_id": ToolArgInfo(desc="机器ID，如'master_host'", type="str")},
        required_args=["machine_id"],
    )
    async def switch_machine_tool(
        machine_id: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.switch_machine(machine_id)

    @toolset.register_tool(
        name="connect_bash_as_machine",
        desc="连接已经打开的任何bash进程，部署jsonrpc远控进程并操控，可用于sudo bash, docker exec -it sh, adb shell, nc -l等任何场景打开的bash",
        args={
            "machine_id": ToolArgInfo(desc="新机器的ID", type="str"),
            "pid": ToolArgInfo(desc="要连接的bash进程PID", type="str"),
            "source_machine": ToolArgInfo(
                desc="进程所在的机器ID，默认当前机器", type="str"
            ),
        },
        required_args=["machine_id", "pid"],
        conflict_with=None,
    )
    async def connect_bash_as_machine_tool(
        machine_id: str,
        pid: str,
        source_machine: Optional[str] = None,
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.add_bash_machine(machine_id, pid, source_machine)

    @toolset.register_tool(
        name="list_remote_configs",
        desc="列出所有预设的远程机器配置",
        args={},
        required_args=[],
    )
    async def list_remote_configs_tool() -> ToolResultSuccess:
        return await machine_control.list_remote_configs()

    @toolset.register_tool(
        name="connect_remote_config",
        desc="根据预设的远程机器配置连接远程机器",
        args={
            "name": ToolArgInfo(desc="远程机器配置的名称", type="str"),
        },
        required_args=["name"],
        conflict_with=None,
    )
    async def connect_remote_config_tool(
        name: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.connect_remote_config(name)

    @toolset.register_tool(
        name="connect_ether_ghost_machine",
        desc="连接到EtherGhost webshell机器并添加到可用机器列表",
        args={
            "machine_id": ToolArgInfo(desc="机器ID", type="str"),
            "session_type": ToolArgInfo(
                desc="webshell类型，例如'php_oneliner'", type="str"
            ),
            "connection_args": ToolArgInfo(
                desc="连接参数字典，根据session类型而定",
                type="Dict[str, Any]",
            ),
        },
        required_args=["machine_id", "session_type", "connection_args"],
        conflict_with=None,
    )
    async def connect_ether_ghost_machine_tool(
        machine_id: str,
        session_type: str,
        connection_args: Dict[str, Any],
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.add_ether_ghost_machine(
            machine_id, session_type, connection_args
        )

    @toolset.register_tool(
        name="ether_ghost_get_connection_args_definition",
        desc="获取EtherGhost各session类型所需的连接参数定义",
        args={},
        required_args=[],
    )
    async def ether_ghost_get_connection_args_definition_tool() -> (
        ToolResultSuccess | ToolResultFailed
    ):
        from ether_ghost.core.base import session_type_info

        definition = {}
        for session_type, info in session_type_info.items():
            connection_args = info.get("connection_args", [])
            args_def = {}
            for arg in connection_args:
                args_def[arg["name"]] = {
                    "type": arg.get("type", "str"),
                    "description": arg.get("description", ""),
                    "required": arg.get("required", False),
                    "default": arg.get("default", None),
                }
            definition[session_type] = args_def
        result = {"type": "ether_ghost", "connection_args_definition": definition}
        return ToolResultSuccess(content=json.dumps(result, ensure_ascii=False))

    @toolset.register_tool(
        name="http_request",
        desc="使用httpx库发送HTTP请求并获取响应内容",
        args={
            "method": ToolArgInfo(desc="HTTP方法，如GET、POST", type="str"),
            "url": ToolArgInfo(desc="请求的URL", type="str"),
            "params": ToolArgInfo(
                desc="查询参数（字典形式）",
                type="Optional[Dict[str, Union[str, int, float, bool]]]",
            ),
            "headers": ToolArgInfo(
                desc="请求头（字典形式）", type="Optional[Dict[str, str]]"
            ),
            "data": ToolArgInfo(desc="请求体数据", type="Optional[str]"),
            "follow_redirects": ToolArgInfo(
                desc="是否跟随重定向，默认False", type="bool"
            ),
            "timeout": ToolArgInfo(desc="超时时间（秒），默认60秒", type="int"),
            "auth": ToolArgInfo(
                desc="认证参数，如['username', 'password']",
                type="Optional[tuple[str, str]]",
            ),
            "cookies": ToolArgInfo(desc="Cookie字典", type="Optional[Dict[str, str]]"),
            "json_data": ToolArgInfo(
                desc="JSON数据（与data互斥）", type="Optional[Dict[str, Any]]"
            ),
            "proxy": ToolArgInfo(desc="代理URL", type="Optional[str]"),
            "verify": ToolArgInfo(
                desc="SSL验证，True/False/ssl.SSLContext", type="Optional[bool]"
            ),
        },
        required_args=["method", "url"],
        conflict_with=None,
    )
    async def http_request_tool(
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
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.http_request(
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

    @toolset.register_tool(
        name="change_directory",
        desc="改变当前工作目录",
        args={"directory": ToolArgInfo(desc="目标目录的路径", type="str")},
        required_args=["directory"],
        conflict_with=None,
    )
    async def change_directory_tool(
        directory: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.change_directory(directory)

    @toolset.register_tool(
        name="process_create",
        desc="创建一个进程，等待一段时间后检查状态。如果进程已退出则返回退出码和输出，否则返回运行中状态。",
        args={
            "argv": ToolArgInfo(
                desc='进程参数列表，如["ls", "-l", "-a"]', type="list[str]"
            ),
            "wait_second": ToolArgInfo(
                desc="创建进程后等待的秒数，最多等待时间，为None时使用平台默认值(1秒)",
                type="Optional[float]",
            ),
        },
        required_args=["argv"],
        conflict_with=None,
    )
    async def process_create_tool(
        argv: list[str], wait_second: Optional[float] = None
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        result = await host_control.create_process(argv, wait_second)
        if not result.success:
            return ToolResultFailed(content=result.error or "创建进程失败")
        if result.returncode is None:
            from linhai.agent.lifecycle import Lifecycle

            process = host_control.get_process(result.pid)
            if process is not None and "lifecycle" in machine_control.registry.members:
                lifecycle = machine_control.registry.get_member_typechecked(
                    "lifecycle", Lifecycle
                )
                await lifecycle.after_process_create.trigger(
                    ProcessCreateInfo(
                        process=process,
                        argv=argv,
                        machine_id=machine_control.target_machine,
                        initial_returncode=None,
                    )
                )
            return ToolResultSuccess(
                content=f"<<pid>>{result.pid}<<pid>><<message>>{result.message}<<message>>"
            )
        return ToolResultSuccess(
            content=f"<<pid>>{result.pid}<<pid>><<returncode>>{result.returncode}<<returncode>><<stdout>>{result.stdout}<<stdout>><<stderr>>{result.stderr}<<stderr>>"
        )

    @toolset.register_tool(
        name="process_stdio_write",
        desc="向进程的标准输入写入内容。",
        args={
            "pid": ToolArgInfo(desc="进程ID", type="str"),
            "content": ToolArgInfo(desc="要写入的内容", type="str"),
            "with_enter": ToolArgInfo(desc="是否在末尾添加回车", type="bool"),
        },
        required_args=["pid", "content", "with_enter"],
        conflict_with=None,
    )
    async def process_stdio_write_tool(
        pid: str, content: str, with_enter: bool
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        write_result = await proc.stdio_write(content, with_enter)
        if not write_result.success:
            return ToolResultFailed(content=write_result.error or "写入失败")
        return ToolResultSuccess(content=write_result.message)

    @toolset.register_tool(
        name="process_stdio_read",
        desc="读取进程的标准输出和标准错误内容。",
        args={
            "pid": ToolArgInfo(desc="进程ID", type="str"),
            "timeout": ToolArgInfo(desc="超时时间（秒），默认60秒", type="float"),
        },
        required_args=["pid"],
        conflict_with=None,
    )
    async def process_stdio_read_tool(
        pid: str, timeout: float = 60.0
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        read_result = await proc.stdio_read(timeout)
        if not read_result.success:
            return ToolResultFailed(content=read_result.error or "读取失败")
        stdout_text = Text.from_ansi(
            read_result.stdout.decode("utf-8", errors="replace")
        ).plain
        stderr_text = Text.from_ansi(
            read_result.stderr.decode("utf-8", errors="replace")
        ).plain
        return ToolResultSuccess(
            content=json.dumps(
                {
                    "pid": pid,
                    "success": True,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "exit_note": read_result.exit_note,
                }
            )
        )

    @toolset.register_tool(
        name="process_wait",
        desc="等待进程结束，带超时设置。",
        args={
            "pid": ToolArgInfo(desc="进程ID", type="str"),
            "timeout": ToolArgInfo(desc="超时时间（秒）", type="float"),
        },
        required_args=["pid", "timeout"],
        conflict_with=None,
    )
    async def process_wait_tool(
        pid: str, timeout: float
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        wait_result = await proc.wait(timeout)
        if not wait_result.success:
            return ToolResultFailed(content=wait_result.error or "等待失败")
        return ToolResultSuccess(
            content=f"<<pid>>{pid}<<pid>><<returncode>>{wait_result.returncode}<<returncode>><<stdout>>{wait_result.stdout}<<stdout>><<stderr>>{wait_result.stderr}<<stderr>>"
        )

    @toolset.register_tool(
        name="process_kill",
        desc="杀死进程，可选择优雅终止。",
        args={
            "pid": ToolArgInfo(desc="进程ID", type="str"),
            "graceful": ToolArgInfo(desc="是否优雅终止进程，默认为True", type="bool"),
        },
        required_args=["pid"],
        conflict_with=None,
    )
    async def process_kill_tool(
        pid: str, graceful: bool = True
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        kill_result = await proc.kill(graceful)
        if not kill_result.success:
            return ToolResultFailed(content=kill_result.error or "终止进程失败")
        return ToolResultSuccess(content=kill_result.message or f"进程 {pid} 已终止")

    @toolset.register_tool(
        name="terminal_create",
        desc="在当前机器上新建虚拟终端，返回终端对应的ID。"
        "终端高度固定且不能滚动，会截断命令输出结果，因此没有必要则优先使用process_create",
        args={
            "columns": ToolArgInfo(desc="终端列数，默认80", type="int"),
            "lines": ToolArgInfo(desc="终端行数，默认24", type="int"),
        },
        required_args=[],
        conflict_with=[
            "terminal_send_keys",
            "terminal_send_string",
            "terminal_read_screen",
        ],
    )
    async def create_terminal_tool(
        columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_create(columns, lines)

    @toolset.register_tool(
        name="terminal_send_keys",
        desc="发送按键列表到终端，特殊按键的定义和pyautogui相同，普通按键则传入对应字符，如'a'。如果需要发送ctrl+c等控制字符，请传入对应的控制键名称，如'ctrl+c'、'ctrl+d'等。",
        args={
            "terminal_id": ToolArgInfo(desc="终端ID", type="str"),
            "keys": ToolArgInfo(
                desc='按键名称列表，如["esc", ":", "q", "enter"]', type="list"
            ),
        },
        required_args=["terminal_id", "keys"],
        conflict_with=["terminal_create"],
    )
    async def send_keys_to_terminal_tool(
        terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_send_keys(terminal_id, keys)

    @toolset.register_tool(
        name="terminal_send_string",
        desc="发送命令等字符串到终端",
        args={
            "terminal_id": ToolArgInfo(desc="终端ID", type="str"),
            "string": ToolArgInfo(desc="要发送的字符串", type="str"),
            "with_enter": ToolArgInfo(desc="是否发送enter", type="bool"),
            "wait_seconds": ToolArgInfo(
                desc="等待一段时间后读取最新画面，默认等待0.3秒", type="float"
            ),
        },
        required_args=["terminal_id", "string", "with_enter"],
        conflict_with=["terminal_create"],
    )
    async def send_string_to_terminal_tool(
        terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_send_string(
            terminal_id, string, with_enter, wait_seconds
        )

    @toolset.register_tool(
        name="terminal_read_screen",
        desc="读取当前终端的屏幕内容",
        args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
        required_args=["terminal_id"],
        conflict_with=["terminal_create"],
    )
    async def read_terminal_screen_tool(
        terminal_id: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_read_screen(terminal_id)

    @toolset.register_tool(
        name="terminal_close",
        desc="关闭终端",
        args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
        required_args=["terminal_id"],
        conflict_with=None,
    )
    async def close_terminal_tool(
        terminal_id: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_close(terminal_id)

    @toolset.register_tool(
        name="read_file",
        desc="读取文件。注意 - 优先于grep/sed：在需要读取文件时优先使用此工具带上行号读取整个文件，只有在此工具无法读取所有内容时才考虑使用sed!",
        args={
            "filepath": ToolArgInfo(desc="文件路径", type="str"),
            "show_line_numbers": ToolArgInfo(desc="是否显示行号", type="bool"),
        },
        required_args=["filepath"],
        conflict_with=[],
    )
    async def read_file_tool(
        filepath: str, show_line_numbers: bool = False
    ) -> Union[ToolResultSuccess, ToolResultFailed, FileContentMessage]:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.read_file(filepath, show_line_numbers)

    @toolset.register_tool(
        name="write_file",
        desc="写入文件内容。"
        "注意：不要复述已有的文件内容！"
        "如果需要复制必须优先使用shell指令cp！"
        "如果需要修改文件必须优先使用replace_file_content！"
        "如果需要追加文件内容，用replace_file_content匹配文件末尾几行并追加！",
        args={
            "filepath": ToolArgInfo(desc="文件路径", type="str"),
            "content": ToolArgInfo(desc="要写入的内容", type="str"),
            "override": ToolArgInfo(desc="是否覆盖已有文件", type="bool"),
        },
        required_args=["filepath", "content"],
        conflict_with=[],
    )
    async def write_file_tool(
        filepath: str, content: str, override: bool = False
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.write_file(filepath, content, override)

    @toolset.register_tool(
        name="replace_file_content",
        desc="替换文件内容中的指定字符串。建议：在修改文件原有内容时优先使用此工具。"
        "追加、添加内容时：优先使用此工具。使用方法为匹配末尾的几行并添加新内容。",
        args={
            "filepath": ToolArgInfo(desc="文件路径", type="str"),
            "old": ToolArgInfo(desc="要替换的字符串", type="str"),
            "new": ToolArgInfo(desc="新的字符串", type="str"),
            "replace_times": ToolArgInfo(
                desc="替换次数，正数代表替换次数，-1代表替换所有，默认不提供时验证旧内容只出现一次",
                type="int",
            ),
        },
        required_args=["filepath", "old", "new"],
        conflict_with=[],
    )
    async def replace_file_content_tool(
        filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.replace_file_content(
            filepath, old, new, replace_times
        )

    @toolset.register_tool(
        name="list_files",
        desc="列出指定文件夹中的文件(使用./表示当前文件夹)",
        args={
            "dirpath": ToolArgInfo(desc="文件夹路径，使用./表示当前目录", type="str")
        },
        required_args=["dirpath"],
        conflict_with=None,
    )
    async def list_files_tool(dirpath: str) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.list_files(dirpath)

    @toolset.register_tool(
        name="get_absolute_path",
        desc="获取路径的绝对路径",
        args={"path": ToolArgInfo(desc="相对或绝对路径", type="str")},
        required_args=["path"],
        conflict_with=None,
    )
    async def get_absolute_path_tool(
        path: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.get_absolute_path(path)

    @toolset.register_tool(
        name="read_file_with_sed",
        desc="执行sed表达式并返回输出，不修改文件",
        args={
            "expression": ToolArgInfo(desc="sed表达式，如: 1,1000p", type="str"),
            "filepath": ToolArgInfo(desc="文件路径", type="str"),
        },
        required_args=["expression", "filepath"],
        conflict_with=[],
    )
    async def read_file_with_sed_tool(
        expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.read_file_with_sed(expression, filepath)

    @toolset.register_tool(
        name="transfer_file",
        desc="将文件从一台机器传送到另一台机器上",
        args={
            "from_filepath": ToolArgInfo(desc="源文件路径", type="str"),
            "from_machine": ToolArgInfo(desc="源机器ID", type="str"),
            "to_filepath": ToolArgInfo(desc="目标文件路径", type="str"),
            "to_machine": ToolArgInfo(desc="目标机器ID", type="str"),
        },
        required_args=[
            "from_filepath",
            "from_machine",
            "to_filepath",
            "to_machine",
        ],
        conflict_with=None,
    )
    async def transfer_file_tool(
        from_filepath: str,
        from_machine: str,
        to_filepath: str,
        to_machine: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.transfer_file(
            from_filepath, from_machine, to_filepath, to_machine
        )

    return toolset
