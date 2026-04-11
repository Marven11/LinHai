"""MachineControl类，负责管理多个机器控制类并注册工具。"""

import json
from typing import Dict, Optional, Protocol, Union, Any, Literal
from linhai.machine_control.http_message import HttpMessage
from linhai.machine_control.process import Process
from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage, FileContentMessage
from linhai.llm import Message
from linhai.registry import Registry
from linhai.tool.base import (
    ToolArgInfo,
    ToolResultSuccess,
    ToolResultFailed,
    ToolSet,
)
from linhai.utils.common import UiNotice
from .master_host.master_host import MasterHostControl
from .ssh_host.ssh_host import SshMachineControl


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
        name="connect_ssh_machine",
        desc="连接到SSH机器并添加到可用机器列表",
        args={
            "machine_id": ToolArgInfo(desc="机器ID", type="str"),
            "host": ToolArgInfo(desc="SSH主机地址", type="str"),
            "port": ToolArgInfo(desc="SSH端口，默认22", type="int"),
            "username": ToolArgInfo(desc="SSH用户名，默认当前用户", type="str"),
        },
        required_args=["machine_id", "host"],
        conflict_with=None,
    )
    async def connect_ssh_machine_tool(
        machine_id: str,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
    ) -> ToolResultSuccess | ToolResultFailed:
        return await machine_control.add_ssh_machine(machine_id, host, port, username)

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
        import json

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
        process = await host_control.create_process(argv, wait_second)
        pid = process.pid
        if process.returncode is not None:
            result = await process.stdio_read(timeout=2.0)
            if isinstance(result, ToolResultFailed):
                return result
            data = json.loads(result.content)
            return ToolResultSuccess(
                content=f"<<pid>>{pid}<<pid>><<returncode>>{process.returncode}<<returncode>><<stdout>>{data.get('stdout', '')}<<stdout>><<stderr>>{data.get('stderr', '')}<<stderr>>"
            )
        result = await process.stdio_read(timeout=2.0)
        if isinstance(result, ToolResultFailed):
            return result
        data = json.loads(result.content)
        stdout_str = data.get("stdout", "")
        stderr_str = data.get("stderr", "")
        message = f"等待失败，程序在{wait_second}秒后在运行。"
        if stdout_str or stderr_str:
            message += f" 至今为止该进程已输出到stdout/stderr的内容：\nstdout:\n{stdout_str}\nstderr:\n{stderr_str}"
        else:
            message += " 建议使用process_*系列工具进行读写stdio或者进一步等待程序"
        return ToolResultSuccess(
            content=f"<<pid>>{pid}<<pid>><<message>>{message}<<message>>"
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
        process = host_control.get_process(pid)
        if process is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        return await process.stdio_write(content, with_enter)

    @toolset.register_tool(
        name="process_stdio_read",
        desc="读取进程的标准输出和标准错误内容。",
        args={
            "pid": ToolArgInfo(desc="进程ID", type="str"),
            "unescape_ansi": ToolArgInfo(
                desc="是否反转义ANSI序列，默认为True", type="bool"
            ),
            "timeout": ToolArgInfo(desc="超时时间（秒），默认60秒", type="float"),
        },
        required_args=["pid"],
        conflict_with=None,
    )
    async def process_stdio_read_tool(
        pid: str, unescape_ansi: bool = True, timeout: float = 60.0
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        process = host_control.get_process(pid)
        if process is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        return await process.stdio_read(unescape_ansi, timeout)

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
        process = host_control.get_process(pid)
        if process is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        return await process.wait(timeout)

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
        process = host_control.get_process(pid)
        if process is None:
            return ToolResultFailed(content=f"进程不存在: {pid}")
        return await process.kill(graceful)

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
        name="modify_file_with_sed",
        desc="使用sed表达式修改文件，支持mac和linux的区别",
        args={
            "expression": ToolArgInfo(desc="sed表达式", type="str"),
            "filepath": ToolArgInfo(desc="文件路径", type="str"),
        },
        required_args=["expression", "filepath"],
        conflict_with=[],
    )
    async def modify_file_with_sed_tool(
        expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.modify_file_with_sed(expression, filepath)

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


class HostControl(Protocol):
    """主机控制协议，所有机器控制类必须实现此接口。"""

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
    ) -> HttpMessage | ToolResultFailed: ...

    async def change_directory(
        self, directory: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def create_process(
        self, argv: list[str], wait_second: Optional[float] = None
    ) -> Process: ...

    def get_process(self, pid: str) -> Process | None: ...

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> Union[ToolResultSuccess, ToolResultFailed, FileContentMessage]: ...

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def list_files(
        self, dirpath: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def get_absolute_path(
        self, path: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def modify_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def get_terminals(self) -> ToolResultSuccess | ToolResultFailed: ...

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> ToolResultSuccess | ToolResultFailed: ...

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> ToolResultSuccess | ToolResultFailed: ...


class MachineControl:
    """机器控制管理器，负责注册工具和切换机器。"""

    def __init__(self, registry: Registry, tmux_terminal: bool = True):
        self.registry = registry
        self.target_machine = "master_host"
        self.machines: Dict[str, HostControl] = {
            "master_host": MasterHostControl(registry, tmux_terminal=tmux_terminal),
        }
        self.machine_descriptions: Dict[str, str] = {
            "master_host": "本地主机",
        }
        registry.register_member("machine_control", self)

    async def switch_machine(
        self, machine_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id not in self.machines:
            return ToolResultFailed(content=f"机器未找到: {machine_id}")

        old_machine_id = self.target_machine
        self.target_machine = machine_id

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"已切换机器: {old_machine_id} -> {machine_id}"
            ),
        )

        return ToolResultSuccess(content=f"已切换到机器: {machine_id}")

    async def add_ssh_machine(
        self,
        machine_id: str,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id in self.machines:
            return ToolResultFailed(content=f"机器ID已存在: {machine_id}")

        ssh_control = SshMachineControl(
            host=host, registry=self.registry, port=port, username=username
        )

        try:
            connected = await ssh_control.connect()
            if not connected:
                return ToolResultFailed(content=f"连接SSH机器失败: {host}:{port}")
        except Exception as e:
            return ToolResultFailed(content=f"连接SSH机器时出错: {e}")

        self.machines[machine_id] = ssh_control
        self.machine_descriptions[machine_id] = f"SSH远程主机 ({host}:{port})"

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"SSH连接成功: 已连接到远程机器 {machine_id} ({host}:{port}), 用户名 {username}",
            ),
        )

        return ToolResultSuccess(
            content=f"已成功添加SSH机器: {machine_id} ({host}:{port})"
        )

    async def add_ether_ghost_machine(
        self,
        machine_id: str,
        session_type: str,
        connection_args: Dict[str, Any],
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id in self.machines:
            return ToolResultFailed(content=f"机器ID已存在: {machine_id}")

        from .ether_ghost_host.ether_ghost_host import EtherGhostMachineControl

        ether_control = EtherGhostMachineControl(
            session_type=session_type,
            connection_args=connection_args,
            machine_id=machine_id,
        )
        await ether_control.initialize()

        self.machines[machine_id] = ether_control
        self.machine_descriptions[machine_id] = (
            f"EtherGhost webshell主机 (类型: {session_type})"
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"EtherGhost连接成功: 已连接到远程机器 {machine_id} (session类型: {session_type})",
            ),
        )

        return ToolResultSuccess(
            content=f"已成功添加EtherGhost机器: {machine_id} (session类型: {session_type})"
        )

    async def list_all_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        """列出所有机器上的所有终端"""
        all_terminals = []
        for machine_id, host_control in self.machines.items():
            result = await host_control.get_terminals()
            if isinstance(result, ToolResultFailed):
                return ToolResultFailed(
                    content=f"获取机器 {machine_id} 的终端列表失败: {result.content}"
                )

            if result.content:
                all_terminals.append(f"机器 {machine_id}:\n{result.content}")

        if not all_terminals:
            content = "当前所有机器上都没有终端"
        else:
            content = "\n\n".join(all_terminals)

        return ToolResultSuccess(content=content)

    async def list_machines(self) -> ToolResultSuccess:
        lines = ["可用机器:"]
        for machine_id, description in self.machine_descriptions.items():
            current = " (当前)" if machine_id == self.target_machine else ""
            lines.append(f"  - {machine_id}: {description}{current}")

        return ToolResultSuccess(content="\n".join(lines))

    async def transfer_file(
        self,
        from_filepath: str,
        from_machine: str,
        to_filepath: str,
        to_machine: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        """将文件从一台机器传输到另一台机器。

        Args:
            from_filepath: 源文件路径
            from_machine: 源机器ID
            to_filepath: 目标文件路径
            to_machine: 目标机器ID

        Returns:
            执行结果
        """
        try:
            import tempfile
            import os

            if from_machine == to_machine:
                return ToolResultFailed(content=f"源机器和目标机器相同: {from_machine}")

            if from_machine not in self.machines:
                return ToolResultFailed(content=f"源机器不存在: {from_machine}")
            if to_machine not in self.machines:
                return ToolResultFailed(content=f"目标机器不存在: {to_machine}")

            from_control = self.machines[from_machine]
            to_control = self.machines[to_machine]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".transfer") as tmp:
                temp_path = tmp.name

            try:
                if hasattr(from_control, "download_file_concurrent"):
                    download_result = await from_control.download_file_concurrent(
                        from_filepath, temp_path
                    )
                else:
                    download_result = ToolResultFailed(
                        content=f"源机器 {from_machine} 不支持文件下载"
                    )

                if isinstance(download_result, ToolResultFailed):
                    return ToolResultFailed(
                        content=f"从源机器下载文件失败: {download_result.content}"
                    )

                with open(temp_path, "rb") as f:
                    file_data = f.read()

                if hasattr(to_control, "upload_file_concurrent"):
                    upload_result = await to_control.upload_file_concurrent(
                        file_data, to_filepath
                    )
                else:
                    upload_result = ToolResultFailed(
                        content=f"目标机器 {to_machine} 不支持文件上传"
                    )

                if isinstance(upload_result, ToolResultFailed):
                    return ToolResultFailed(
                        content=f"向目标机器上传文件失败: {upload_result.content}"
                    )

                return ToolResultSuccess(
                    content=f"文件传输成功: {from_machine}:{from_filepath} -> {to_machine}:{to_filepath}"
                )

            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            return ToolResultFailed(content=f"文件传输失败: {e}")

    def register_plugin(self, lifecycle: "Lifecycle"):
        """注册插件到lifecycle。"""
        plugin = MachineControlPlugin(self.registry, self)
        plugin.register(lifecycle)


class MachineControlPlugin:
    """MachineControl的插件，用于添加当前机器提示和on_machine使用警告。"""

    def __init__(self, registry: Registry, machine_control: MachineControl):
        self.registry = registry
        self.machine_control = machine_control
        self.consecutive_same_on_machine_count = 0
        self.last_on_machine: Optional[str] = None

    async def before_message_generation(self):
        """在消息生成前更新notification_message。"""
        agent = self.registry.get_member_typechecked("agent", Agent)
        agent.message_processor.update_notification_message(
            RuntimeMessage(f"当前在{self.machine_control.target_machine}上"),
            source="machine_control",
            sort_value=0,
        )

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """处理工具调用的结果，合并了原来的before_tool_call和after_tool_call功能。"""
        from linhai.utils.common import UiNotice

        if status == "skipped":

            if "on_machine" in toolcall_arguments:
                on_machine = toolcall_arguments["on_machine"]
                if on_machine is not None:
                    current_machine = self.machine_control.target_machine
                    if on_machine != current_machine:
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="INFO",
                                content=f"正在切换到机器 {on_machine} 执行工具 {tool_name}",
                            ),
                        )
            return None

        elif status == "success":

            if "on_machine" in toolcall_arguments:
                on_machine = toolcall_arguments["on_machine"]
                current_machine = self.machine_control.target_machine

                if on_machine is None or on_machine != current_machine:

                    self.consecutive_same_on_machine_count = 0
                    self.last_on_machine = None
                else:

                    if self.last_on_machine == on_machine:
                        self.consecutive_same_on_machine_count += 1
                    else:
                        self.consecutive_same_on_machine_count = 1
                        self.last_on_machine = on_machine

                    if self.consecutive_same_on_machine_count >= 3:
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"连续{self.consecutive_same_on_machine_count}次工具调用都指定了相同的on_machine '{on_machine}'，且未切换机器。请确认是否需要频繁指定。",
                            ),
                        )
            return None

        else:
            return None

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)
        lifecycle.after_toolcall.register(self.after_toolcall)
