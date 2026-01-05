"""MachineControl类，负责管理多个机器控制类并注册工具。"""

from typing import Dict, Optional, Protocol, Union, Tuple
from linhai.agent import Agent
from linhai.agent.base import RuntimeMessage
from linhai.llm import Message
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolArgInfo, ToolResultMessage, ToolErrorMessage, ToolSet
from linhai.utils import CliRuntimeNotice
from .master_host.master_host import MasterHostControl
from .ssh_host.ssh_host import SshMachineControl


class MachineControlToolSet(ToolSet):
    """MachineControl专用的工具集，避免闭包变量问题。"""

    def __init__(self, machine_control: "MachineControl"):
        super().__init__()
        self.machine_control = machine_control
        self._register_all_tools()

    def _register_all_tools(self):
        """注册所有工具"""

        @self.register_tool(
            name="list_machines",
            desc="列出所有可用的机器",
            args={},
            required_args=[],
        )
        async def list_machines_tool() -> ToolResultMessage | ToolErrorMessage:
            return await self.machine_control.list_machines()

        @self.register_tool(
            name="switch_machine",
            desc="切换到指定机器",
            args={
                "machine_id": ToolArgInfo(desc="机器ID，如'master_host'", type="str")
            },
            required_args=["machine_id"],
        )
        async def switch_machine_tool(
            machine_id: str,
        ) -> ToolResultMessage | ToolErrorMessage:
            return await self.machine_control.switch_machine(machine_id)

        @self.register_tool(
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
        ) -> ToolResultMessage | ToolErrorMessage:
            return await self.machine_control.add_ssh_machine(
                machine_id, host, port, username
            )

        @self.register_tool(
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
                    desc="是否跟随重定向，默认True", type="bool"
                ),
                "timeout": ToolArgInfo(
                    desc="超时时间（秒），默认60秒", type="int"
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
            follow_redirects: bool = True,
            timeout: int = 60,
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.http_request(
                method, url, params, headers, data, follow_redirects, timeout
            )

        @self.register_tool(
            name="run_command",
            desc="执行系统命令。可以执行shell命令，但使用时务必谨慎，避免损坏用户电脑。",
            args={
                "command": ToolArgInfo(
                    desc="要执行的命令字符串，如 'ls | grep test'", type="str"
                ),
                "timeout": ToolArgInfo(desc="超时时间（秒），默认30秒", type="float"),
            },
            required_args=["command"],
            conflict_with=None,
        )
        async def run_command_tool(command: str, timeout: float = 30.0) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.run_command(command, timeout)

        @self.register_tool(
            name="change_directory",
            desc="改变当前工作目录",
            args={"directory": ToolArgInfo(desc="目标目录的路径", type="str")},
            required_args=["directory"],
            conflict_with=None,
        )
        async def change_directory_tool(directory: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.change_directory(directory)

        @self.register_tool(
            name="terminal_create",
            desc="新建虚拟终端，返回终端对应的ID，这个工具不能和其他工具一起调用！",
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
        async def create_terminal_tool(columns: int = 80, lines: int = 24) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.terminal_create(columns, lines)

        @self.register_tool(
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
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.terminal_send_keys(terminal_id, keys)

        @self.register_tool(
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
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.terminal_send_string(
                terminal_id, string, with_enter, wait_seconds
            )

        @self.register_tool(
            name="terminal_read_screen",
            desc="读取当前终端的屏幕内容",
            args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
            required_args=["terminal_id"],
            conflict_with=["terminal_create"],
        )
        async def read_terminal_screen_tool(terminal_id: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.terminal_read_screen(terminal_id)

        @self.register_tool(
            name="terminal_close",
            desc="关闭终端",
            args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
            required_args=["terminal_id"],
            conflict_with=None,
        )
        async def close_terminal_tool(terminal_id: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.terminal_close(terminal_id)

        @self.register_tool(
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
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.read_file(filepath, show_line_numbers)

        @self.register_tool(
            name="write_file",
            desc="写入文件内容。注意：避免输出大量重复内容！修改文件时优先使用replace_file_content或者append_file，复制文件优先使用shell指令",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "content": ToolArgInfo(desc="要写入的内容", type="str"),
                "override": ToolArgInfo(desc="是否覆盖已有文件", type="bool"),
            },
            required_args=["filepath", "content"],
            conflict_with=[
                "read_file",
                "read_file_with_sed",
            ],
        )
        async def write_file_tool(
            filepath: str, content: str, override: bool = False
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.write_file(filepath, content, override)

        @self.register_tool(
            name="append_file",
            desc="追加文件内容。建议：在增加文件内容时优先考虑使用此工具或insert工具",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "content": ToolArgInfo(desc="要在文件后追加的内容", type="str"),
                "assume_empty_line": ToolArgInfo(
                    desc="是否假设文件以空行结尾，默认为true", type="bool"
                ),
            },
            required_args=["filepath", "content"],
            conflict_with=[
                "read_file",
                "read_file_with_sed",
            ],
        )
        async def append_file_tool(
            filepath: str, content: str, assume_empty_line: bool = True
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.append_file(filepath, content, assume_empty_line)

        @self.register_tool(
            name="replace_file_content",
            desc="替换文件内容中的指定字符串。建议：在修改文件原有内容时优先使用此工具重要：为确保修改准确性，必须提供包含完整上下文（至少前后5行）的唯一标识字符串。避免对同一文件多次调用此工具修改相同位置，这可能导致意外结果。",
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
            conflict_with=[
                "read_file",
                "read_file_with_sed",
            ],
        )
        async def replace_file_content_tool(
            filepath: str, old: str, new: str, replace_times: Optional[int] = None
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.replace_file_content(
                filepath, old, new, replace_times
            )

        @self.register_tool(
            name="list_files",
            desc="列出指定文件夹中的文件(使用./表示当前文件夹)",
            args={
                "dirpath": ToolArgInfo(
                    desc="文件夹路径，使用./表示当前目录", type="str"
                )
            },
            required_args=["dirpath"],
            conflict_with=None,
        )
        async def list_files_tool(dirpath: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.list_files(dirpath)

        @self.register_tool(
            name="get_absolute_path",
            desc="获取路径的绝对路径",
            args={"path": ToolArgInfo(desc="相对或绝对路径", type="str")},
            required_args=["path"],
            conflict_with=None,
        )
        async def get_absolute_path_tool(path: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.get_absolute_path(path)

        @self.register_tool(
            name="read_file_with_sed",
            desc="执行sed表达式并返回输出，不修改文件",
            args={
                "expression": ToolArgInfo(desc="sed表达式，如: 1,1000p", type="str"),
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
            },
            required_args=["expression", "filepath"],
            conflict_with=[],
        )
        async def read_file_with_sed_tool(expression: str, filepath: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.read_file_with_sed(expression, filepath)

        @self.register_tool(
            name="modify_file_with_sed",
            desc="使用sed表达式修改文件，支持mac和linux的区别",
            args={
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
            },
            required_args=["expression", "filepath"],
            conflict_with=[
                "read_file",
                "read_file_with_sed",
            ],
        )
        async def modify_file_with_sed_tool(expression: str, filepath: str) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.modify_file_with_sed(expression, filepath)

        @self.register_tool(
            name="insert_at_line",
            desc="将内容插入到文件的指定行号位置。内容将会插入到原有行之前，如行号为1则插入到开头，行号为2则插入到第二行之前，第一行之后。建议：在插入新内容时优先使用此工具，但是在多次修改文件时行号容易变化，此时不要使用此工具以避免出错。注意：调用时需提供预期插入位置的当前行内容（不含换行符）以验证行号准确性。",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "line_number": ToolArgInfo(desc="要插入的行号（从1开始）", type="int"),
                "content": ToolArgInfo(desc="要插入的内容", type="str"),
                "expected_line_content": ToolArgInfo(
                    desc="预期插入位置的当前行内容（不含换行符）", type="str"
                ),
            },
            required_args=[
                "filepath",
                "line_number",
                "content",
                "expected_line_content",
            ],
            conflict_with=[
                "read_file",
                "read_file_with_sed",
            ],
        )
        async def insert_at_line_tool(
            filepath: str, line_number: int, content: str, expected_line_content: str
        ) -> Message:
            host_control = self.machine_control.machines[
                self.machine_control.target_machine
            ]
            return await host_control.insert_at_line(
                filepath, line_number, content, expected_line_content
            )


def register_machine_control_tools(machine_control: "MachineControl") -> ToolSet:
    """注册所有工具"""
    return MachineControlToolSet(machine_control)


class HostControl(Protocol):
    """主机控制协议，所有机器控制类必须实现此接口。"""

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = True,
        timeout: int = 60,
    ) -> Message: ...

    async def run_command(self, command: str, timeout: float = 30.0) -> Message: ...

    async def change_directory(self, directory: str) -> Message: ...

    async def terminal_create(self, columns: int = 80, lines: int = 24) -> Message: ...

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> Message: ...

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> Message: ...

    async def terminal_read_screen(self, terminal_id: str) -> Message: ...

    async def terminal_close(self, terminal_id: str) -> Message: ...

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> Message: ...

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> Message: ...

    async def append_file(
        self, filepath: str, content: str, assume_empty_line: bool = True
    ) -> Message: ...

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> Message: ...

    async def list_files(self, dirpath: str) -> Message: ...

    async def get_absolute_path(self, path: str) -> Message: ...

    async def read_file_with_sed(self, expression: str, filepath: str) -> Message: ...

    async def modify_file_with_sed(self, expression: str, filepath: str) -> Message: ...

    async def insert_at_line(
        self,
        filepath: str,
        line_number: int,
        content: str,
        expected_line_content: str,
    ) -> Message: ...


class MachineControl:
    """机器控制管理器，负责注册工具和切换机器。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.target_machine = "master_host"
        self.machines: Dict[str, HostControl] = {
            "master_host": MasterHostControl(),
        }
        self.machine_descriptions: Dict[str, str] = {
            "master_host": "本地主机",
        }
        group_chat.register_member("machine_control", self)

    async def switch_machine(
        self, machine_id: str
    ) -> ToolResultMessage | ToolErrorMessage:
        if machine_id not in self.machines:
            return ToolErrorMessage(f"机器未找到: {machine_id}")

        old_machine_id = self.target_machine
        self.target_machine = machine_id

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"已切换机器: {old_machine_id} -> {machine_id}"
            ),
        )

        return ToolResultMessage(f"已切换到机器: {machine_id}")

    async def add_ssh_machine(
        self,
        machine_id: str,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
    ) -> ToolResultMessage | ToolErrorMessage:
        if machine_id in self.machines:
            return ToolErrorMessage(f"机器ID已存在: {machine_id}")

        ssh_control = SshMachineControl(
            host=host, group_chat=self.group_chat, port=port, username=username
        )

        # 尝试连接
        try:
            connected = await ssh_control.connect()
            if not connected:
                return ToolErrorMessage(f"连接SSH机器失败: {host}:{port}")
        except Exception as e:
            return ToolErrorMessage(f"连接SSH机器时出错: {e}")

        self.machines[machine_id] = ssh_control
        self.machine_descriptions[machine_id] = f"SSH远程主机 ({host}:{port})"

        # 发送CliRuntimeNotice提醒用户SSH连接成功
        actual_username = username if username is not None else ssh_control.username
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"SSH连接成功: 已连接到远程机器 {machine_id} ({host}:{port}), 用户名 {actual_username}",
            ),
        )

        return ToolResultMessage(f"已成功添加SSH机器: {machine_id} ({host}:{port})")

    async def list_machines(self) -> ToolResultMessage:
        lines = ["可用机器:"]
        for machine_id, description in self.machine_descriptions.items():
            current = " (当前)" if machine_id == self.target_machine else ""
            lines.append(f"  - {machine_id}: {description}{current}")

        return ToolResultMessage("\n".join(lines))

    def register_plugin(self, lifecycle):
        """注册插件到lifecycle。"""
        # 创建一个插件，用于在appending_message中添加当前机器提示
        plugin = MachineControlPlugin(self.group_chat, self)
        plugin.register(lifecycle)


class MachineControlPlugin:
    """MachineControl的插件，用于添加当前机器提示。"""

    def __init__(self, group_chat: GroupChat, machine_control: MachineControl):
        self.group_chat = group_chat
        self.machine_control = machine_control

    async def before_message_generation(self, *_args, **_kwargs):
        """在消息生成前更新appending_message。"""
        agent = self.group_chat.get_members("agent", Agent)
        agent.message_processor.update_appending_message(
            RuntimeMessage(f"当前在{self.machine_control.target_machine}上"),
            source="machine_control",
            sort_value=0
        )

    def register(self, lifecycle):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
