"""文件操作管理插件。"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Union
import reprlib
import time

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import (
    FileContentMessage,
    RuntimeMessage,
    GlobalMemory,
    PathMemory,
)
from linhai.tool.base import ToolCallResultMessage
from linhai.group_chat import GroupChat
from linhai.machine_control import MachineControl
from linhai.utils import CliRuntimeNotice
from linhai.llm import Message

from .helpers import (
    READ_FILE_COMMANDS,
    is_small_file,
    is_already_read,
    is_existing_file,
)

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    @abstractmethod
    def register(self, lifecycle: "Lifecycle") -> None:
        """将Plugin注册到Lifecycle中。"""


class DuplicateFileReadPlugin(Plugin):
    """拦截重复文件读取以优化代理行为。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.counter = 0

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_on_tool_result(self.on_tool_result)

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """工具调用结果回调，检查是否重复读取文件。"""
        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        if status != "success":
            return None

        if tool_name != "read_file":
            return None


        filepath = toolcall_arguments.get("filepath")
        if not filepath:
            return None

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            return None

        recent_file_messages = []
        for msg in reversed(list(agent.message_processor.get_messages())):
            if not isinstance(msg, FileContentMessage):
                continue
            try:
                if str(Path(msg.filepath).resolve()) == str(Path(filepath).resolve()):
                    recent_file_messages.append(msg)
            except (OSError, ValueError):
                continue

        if recent_file_messages:
            latest_message = recent_file_messages[0]

            if message is None:
                return None
            actual_content = str(message.to_llm_message().get("content", ""))

            if message == latest_message:
                self.counter += 1
                if self.counter == 1:
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content="模型第一次重复读取相同文件，已警告",
                        ),
                    )
                    reprobj = reprlib.Repr(maxstring=100)
                    preview = reprobj.repr(actual_content)
                    agent.message_processor.add_new_message(
                        RuntimeMessage(
                            f"警告：你已经读取过文件{filepath}，内容和上一次完全相同，这是第一次警告！\n"
                            f"文件内容预览：{preview}\n"
                            f"不要重复读取文件拖延时间！你应该立即修改文件而不是继续拖延！"
                        )
                    )
                    return None
                else:
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content="模型第二次重复读取相同文件，已阻止",
                        ),
                    )
                    reprobj = reprlib.Repr(maxstring=100)
                    preview = reprobj.repr(actual_content)
                    return RuntimeMessage(
                        f"错误：你已经读取过文件{filepath}，内容和上一次完全相同，本条重复内容已自动隐藏。\n"
                        f"警告：你已经重复读取{self.counter}次文件！这是非常低效的行为！立即停止重复读取！{"！！！" * self.counter}"
                        f"文件内容预览：{preview}\n"
                        f"不要重复读取文件拖延时间！你应该立即修改文件而不是继续拖延！"
                    )
            else:
                self.counter = 0
                return None

        self.counter = 0
        return None


class UnnecessarySedReadPlugin(Plugin):
    """拦截不必要的sed调用插件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.warning_count = 0
        self.last_reset_time = time.time()

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_on_tool_result(self.on_tool_result)

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """工具调用后回调，检查是否不必要的小块读取。"""
        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        if status != "success":
            return None

        if tool_name == "read_file":
            self.warning_count = 0
            return None

        if tool_name != "read_file_with_sed":
            return None



        filepath = toolcall_arguments.get("filepath")
        if not filepath:
            return None

        agent = self.group_chat.get_members("agent", Agent)

        is_small = await is_small_file(filepath)
        is_already = await is_already_read(agent, filepath)

        if not is_small and not is_already:
            return None

        self.warning_count += 1

        if self.warning_count >= 3:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="模型多次小块读取代码文件，已阻止",
                ),
            )
            return RuntimeMessage(
                "错误：不使用read_file直接读取文件而是滥用read_file_with_sed多次小块读取代码文件\n"
                "警告：本插件会一直阻止你重复读取文件，直到你开始改代码为止！\n"
                "建议：如果需要查看对应内容的行号，使用show_line参数读取整个文件；"
                "如果需要查看修改过的文件，使用read_file重新读取！"
            )
        else:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="模型多次小块读取代码文件，已警告",
                ),
            )
            return RuntimeMessage(
                f"警告：检测到不必要的sed读取（第{self.warning_count}次警告）。建议直接使用read_file读取整个文件。"
            )


class UnnecessaryRunCommandPlugin(Plugin):
    """拦截不必要的process_create调用插件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.warning_count = 0
        self.last_reset_time = time.time()

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_on_tool_result(self.on_tool_result)

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """工具调用后回调，检查是否不必要的process_create用于读取已读文件。"""
        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        if status != "success":
            return None

        if tool_name != "process_create":
            return None



        command_list = toolcall_arguments.get("command", [])

        if not command_list:
            return None

        cmd = command_list[0]
        if cmd not in READ_FILE_COMMANDS:
            return None

        agent = self.group_chat.get_members("agent", Agent)

        file_args = []
        for arg in command_list[1:]:
            if is_existing_file(arg):
                file_args.append(arg)

        if not file_args:
            return None

        for filepath in file_args:
            if await is_already_read(agent, filepath):
                self.warning_count += 1
                if self.warning_count >= 3:
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content="模型多次使用process_create读取已读文件，已阻止",
                        ),
                    )
                    return RuntimeMessage(
                        "错误：不使用read_file直接读取文件而是滥用process_create多次读取已读文件\n"
                        "警告：本插件会一直阻止你重复读取文件，直到你开始改代码为止！\n"
                        "建议：如果需要查看文件内容，使用read_file工具；"
                        "如果需要执行命令，确保命令必要且文件未重复读取。"
                    )
                else:
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"模型使用process_create读取已读文件，已警告（第{self.warning_count}次）",
                        ),
                    )
                    return RuntimeMessage(
                        f"警告：检测到不必要的process_create用于读取已读文件（第{self.warning_count}次警告）。"
                        f"建议直接使用read_file读取文件。"
                    )
        self.warning_count = 0
        return None


class FileReadWriteConflictPlugin(Plugin):
    """检查读写文件冲突的插件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.read_files: set[str] = set()

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前清空已读取文件列表。"""
        self.read_files.clear()

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """工具结果回调，检查读写文件冲突。"""
        try:
            machine_control = self.group_chat.get_members(
                "machine_control", MachineControl
            )
            if machine_control.target_machine != "master_host":
                return None
        except Exception:
            return None

        if status != "success":
            return None

        read_file_tools = {"read_file", "read_file_with_sed"}
        if tool_name in read_file_tools:
            filepath = (
                toolcall_arguments.get("filepath") if toolcall_arguments else None
            )
            if filepath:
                try:
                    abs_path = str(Path(filepath).resolve())
                    self.read_files.add(abs_path)
                except (OSError, ValueError):
                    pass
            return None

        write_file_tools = {
            "write_file",
            "replace_file_content",
            "modify_file_with_sed",
        }
        if tool_name in write_file_tools:
            filepath = (
                toolcall_arguments.get("filepath") if toolcall_arguments else None
            )
            if not filepath:
                return None

            try:
                abs_path = str(Path(filepath).resolve())
            except (OSError, ValueError):
                return None

            if abs_path in self.read_files:
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content=f"检测到读写文件冲突：在读取文件后立即尝试写入同一文件 {filepath}，已警告",
                    ),
                )
                return RuntimeMessage(
                    f"警告：你刚刚读取了文件{filepath!r}，然后立即尝试修改它。\n"
                    "注意：如果你没有看到文件内容（例如在同一个回答中连续调用多个工具），\n"
                    "这是模型幻觉。你应该先读取文件，查看内容后再决定是否修改。\n"
                    "建议：确保在修改文件之前已经读取并理解了文件内容。"
                )

        return None

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
        lifecycle.register_on_tool_result(self.on_tool_result)


class DirectoryChangePlugin(Plugin):
    """目录更改检测插件，检测当前目录更改并检查特定文件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.last_directory = None

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前检查目录是否更改。"""
        agent = self.group_chat.get_members("agent", Agent)

        context = getattr(agent, "context", {})
        if not context.get("enable_directory_change_detection", False):
            return

        current_directory = Path.cwd().resolve()

        if self.last_directory == current_directory:
            return

        self.last_directory = current_directory

        target_files = ["LINHAI.md", "AGENTS.md", "CLAUDE.md"]
        for filename in target_files:
            filepath = current_directory / filename
            if filepath.exists():
                has_duplicate = any(
                    message.filepath.resolve() == filepath.resolve()
                    for message in agent.message_processor.get_messages()
                    if isinstance(message, (GlobalMemory, PathMemory))
                )
                if not has_duplicate:
                    agent.message_processor.add_new_message(PathMemory(filepath))

    def register(self, lifecycle: "Lifecycle"):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
