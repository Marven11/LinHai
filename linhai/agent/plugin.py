"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod

from pathlib import Path
import re
import reprlib
import time
import bashlex
import bashlex.ast
import bashlex.errors
from typing import Any, ClassVar, Dict, List, Optional, TypeAlias, Union

from linhai.agent import Agent
import linhai.agent as linhai_agent
from linhai.agent.base import GlobalMemory, PathMemory, FileContentMessage
from linhai.group_chat import GroupChat
from linhai.markdown_parser import extract_tool_calls, extract_tool_calls_with_errors
from .base import RuntimeMessage, WAITING_USER_MARKER, PreviousReasoningMessage
from ..llm import Answer, AssistantMessage, OpenAi, ToolCallMessage, UserMessage
from ..utils import CliRuntimeNotice
from linhai.tool.base import ToolResultMessage


AnyMessage = Union[
    AssistantMessage,
    UserMessage,
    ToolCallMessage,
    RuntimeMessage,
    GlobalMemory,
    PathMemory,
    FileContentMessage,
    PreviousReasoningMessage,
    ToolResultMessage,
]


JsonValue: TypeAlias = Union[
    str, int, float, bool, List["JsonValue"], Dict[str, "JsonValue"], None
]


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response, tool_calls
    ):
        """检查等待用户标记的位置和工具调用冲突。"""
        agent = self.group_chat.get_members("agent", Agent)
        has_waiting_marker = WAITING_USER_MARKER in full_response

        if not agent.current_disable_waiting_user_warning:
            if tool_calls and has_waiting_marker:
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                        f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                    )
                )
                return
            if agent.state == "working" and not tool_calls and not has_waiting_marker:
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用），"
                        f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                    )
                )
                return

        if has_waiting_marker:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                agent.state = "waiting_user"

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class WrongEndPlugin(Plugin):
    """禁止输出end of sentence的plugin"""

    async def after_message_generation(
        self,
        _answer: Answer,
        full_response: str,
        _tool_calls,
    ):
        agent = self.group_chat.get_members("agent", Agent)
        regex_result = re.search("<｜end▁of▁[a-z]+｜>", full_response)
        if regex_result:
            agent.message_processor.add_new_message(
                RuntimeMessage(f"警告: 输出了错误的token: {regex_result!r}")
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class PromptFastAgentPlugin(Plugin):
    """禁止minimax m2/glm 4.6疯狂调用工具的插件"""

    MAX_TOOLCALL_COUNT = 5

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.speeding_counter = 0

    async def before_agent_loop(self, agent: "Agent"):
        """在Agent循环开始前添加特定模型提示。"""
        model = await agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility not in [
            "minimax",
            "glm",
        ]:
            return

        agent.message_processor.add_new_message(
            RuntimeMessage(
                f"你现在是{model.compatibility}，必须在调用工具前仔细思考，禁止调用超过{self.MAX_TOOLCALL_COUNT}个工具！"
            )
        )
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"针对性优化: {model.compatibility}禁止调用超过{self.MAX_TOOLCALL_COUNT}个工具",
            ),
        )

        if model.compatibility == "glm":
            agent.message_processor.add_new_message(
                RuntimeMessage("你现在是GLM，必须打开思考模式，仔细思考！")
            )

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前检查目录是否更改。"""
        # 提示逻辑已迁移到before_agent_loop中
        return

    async def after_token_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()
        if not isinstance(model, OpenAi) or model.compatibility not in [
            "minimax",
            "glm",
        ]:
            return False

        if current_content.count("\n```json toolcall") > self.MAX_TOOLCALL_COUNT:
            extra_message = ""
            if self.speeding_counter:
                extra_message = (
                    "从刚刚开始就一直在调用大量工具，你疯了？？？？"
                    + "？！？！" * self.speeding_counter
                )
            agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"禁止超速：你现在是{model.compatibility}，禁止使用超过{self.MAX_TOOLCALL_COUNT}个工具！"
                    + extra_message
                )
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content=f"针对性优化: 阻止{model.compatibility}调用巨量工具",
                ),
            )
            answer.truncate()
            self.speeding_counter += 1
            return False
        self.speeding_counter = 0
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册before_agent_loop和after_token_generation回调。"""
        lifecycle.register_before_agent_loop(self.before_agent_loop)
        lifecycle.register_after_token_generation(self.after_token_generation)


class SlowStartPlugin(Plugin):
    """防止agent在一开始就调用大量工具的插件"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.enabled = True

    async def after_token_generation(
        self, answer: Answer, current_content: str
    ) -> bool:
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        if not self.enabled:
            return False

        if current_content.count("\n```json toolcall") > 5:
            self.enabled = False
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(level="WARNING", content="过量工具调用，已打断"),
            )
            answer.truncate()
            return False

        return False

    async def after_message_generation(
        self, _answer: Answer, _full_response: str, tool_calls: list[dict]
    ):
        if len(tool_calls) < 5:
            self.enabled = False

    def register(self, lifecycle):
        """注册after_token_generation和after_message_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)
        lifecycle.register_after_message_generation(self.after_message_generation)


class WeirdTokenPlugin(Plugin):
    """错误标记检查Plugin。"""

    async def after_token_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """检查`<｜end▁of▁[a-z]+｜>`和minimax的<tool_call>"""
        agent = self.group_chat.get_members("agent", Agent)
        pattern = r"<｜end▁of▁[a-z]+｜>"
        model = await agent.get_current_model()

        for line in current_content.split("\n"):
            if re.search(pattern, line):
                # 使用truncate以保留已经输出的工具调用，避免重复调用
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        "检测到错误结束标记：在一行中有`<｜end▁of▁[a-z]+｜>`且前面都是文字，已截断输出"
                    )
                )
                answer.truncate()
                return False
            if (
                isinstance(model, OpenAi)
                and model.compatibility == "minimax"
                and line == "<tool_call>"
            ):
                await agent.interrupt(
                    "检测到错误工具调用标记：输出了错误的工具调用: <tool_call>\n你应该使用json toolcall代码块调用工具！"
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


class EndThinkPlugin(Plugin):
    """检查输出中是否有只有'</think>'的行并打断agent。"""

    async def after_token_generation(self, _answer: Answer, current_content: str):
        """检查是否有一行只有'</think>'。"""
        agent = self.group_chat.get_members("agent", Agent)

        lines = current_content.split("\n")
        for line in lines:
            if line.strip() == "</think>":
                await agent.interrupt(
                    "错误：检测到只有'</think>'的行，你将两条消息合并成了一条发送！请依次发送每条消息！"
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


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

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)


class SingleToolCallReminderPlugin(Plugin):
    """提醒agent不要连续多次只调用单个工具的插件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.single_tool_call_count = 0

    async def after_message_generation(
        self, _answer: Answer, _full_response: str, tool_calls: list[dict]
    ):
        """检查是否连续多次只调用了一个工具。"""
        agent = self.group_chat.get_members("agent", Agent)

        if len(tool_calls) == 1:
            self.single_tool_call_count += 1

            if self.single_tool_call_count >= 2:
                agent.message_processor.update_appending_message(
                    RuntimeMessage(
                        f"注意：你连续{self.single_tool_call_count}次仅调用一个工具，"
                        "除开特殊原因不要每次只调用一个工具！"
                        + "！！！！！" * (self.single_tool_call_count - 2)
                    ),
                    source="single_tool_call_reminder",
                    sort_value=0,
                )
            else:
                agent.message_processor.update_appending_message(
                    None, source="single_tool_call_reminder", sort_value=0
                )
        else:
            self.single_tool_call_count = 0
            agent.message_processor.update_appending_message(
                None, source="single_tool_call_reminder", sort_value=0
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class OnlyReasoningPlugin(Plugin):
    """针对deepseek v3.2检测是否只思考不输出"""

    async def after_message_generation(
        self,
        answer: Answer,
        full_response: str,
        _tool_calls: List[Dict[str, JsonValue]],
    ):
        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility != "deepseek":
            return

        reasoning_content = answer.get_reasoning_message()

        if reasoning_content and not full_response.strip():
            agent.message_processor.update_appending_message(
                RuntimeMessage(
                    "错误：不要只思考，不输出！你需要在</think>后输出内容以调用工具或回复用户！"
                ),
                source="only_reasoning",
                sort_value=0,
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING", content="模型只思考不输出，已提醒模型"
                ),
            )
        else:
            agent.message_processor.update_appending_message(
                None, source="only_reasoning", sort_value=0
            )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class PreviousReasoningPlugin(Plugin):
    """提供agent最近思考内容的插件。

    在模型支持思考时将PreviousReasoningMessage插入到appending message，
    否则移除。
    """

    async def after_message_generation(
        self,
        _answer: Answer,
        _full_response: str,
        _tool_calls: List[Dict[str, JsonValue]],
    ):
        agent = self.group_chat.get_members("agent", Agent)

        msgs = [
            msg.reasoning_message
            for msg in agent.message_processor.get_messages()
            if isinstance(msg, AssistantMessage) and msg.reasoning_message
        ]
        if msgs:
            previous_reasoning_msg = PreviousReasoningMessage(msgs[-6:])
            agent.message_processor.update_appending_message(
                previous_reasoning_msg, source="previous_reasoning", sort_value=-100
            )
        else:
            agent.message_processor.update_appending_message(
                None, source="previous_reasoning", sort_value=-100
            )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class ToolCallInReasoningPlugin(Plugin):
    """检测思考内容中工具调用的插件。

    当agent在思考内容中包含工具调用时警告agent，
    但如果在实际输出中调用了工具，则不提醒（因为已经实际调用了）。
    """

    async def after_message_generation(
        self,
        answer: Answer,
        _full_response: str,
        tool_calls: List[Dict[str, JsonValue]],
    ):
        """检查推理内容中是否包含工具调用，且实际输出中没有调用工具。"""

        agent = self.group_chat.get_members("agent", Agent)

        reasoning_content = answer.get_reasoning_message()
        if not reasoning_content:
            return

        tool_calls_in_reasoning = extract_tool_calls(reasoning_content)
        if not tool_calls_in_reasoning:
            return

        reasoning_tool_names = {
            str(tool_call.get("name", "未知工具"))
            for tool_call in tool_calls_in_reasoning
        }
        actual_tool_names = {
            str(tool_call.get("name", "未知工具")) for tool_call in tool_calls
        }

        if not reasoning_tool_names.isdisjoint(actual_tool_names):
            return

        tool_names = [
            tool_call.get("name", "未知工具") for tool_call in tool_calls_in_reasoning
        ]
        unique_tool_names = list(set(tool_names))

        if len(unique_tool_names) == 1:
            agent_warning_message = f"警告：你在推理内容中调用了工具'{unique_tool_names[0]}'，但推理内容中的工具调用不会实际执行！"
            ui_warning_message = f"推理内容中检测到工具调用: {unique_tool_names[0]}"
        else:
            agent_warning_message = f"警告：你在推理内容中调用了工具{unique_tool_names}，但推理内容中的工具调用不会实际执行！"
            ui_warning_message = (
                f"推理内容中检测到工具调用: {', '.join(unique_tool_names)}"
            )

        agent.message_processor.add_new_message(RuntimeMessage(agent_warning_message))
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="WARNING", content=ui_warning_message),
        )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class JsonCodeBlockPlugin(Plugin):
    """检测agent误用`json`而非`json toolcall`代码块的插件。"""

    async def after_message_generation(
        self, _answer: Answer, full_response: str, _tool_calls
    ):
        """检查是否有json代码块包含有效的工具调用。"""
        agent = self.group_chat.get_members("agent", Agent)

        json_tool_calls, json_errors = extract_tool_calls_with_errors(
            full_response, language="json"
        )

        if json_tool_calls and not json_errors:
            tool_names = [call.get("name", "未知工具") for call in json_tool_calls]
            unique_tool_names = list(set(tool_names))

            if len(unique_tool_names) == 1:
                warning_msg = f"警告：你使用了`json`代码块而非`json toolcall`代码块调用了工具'{unique_tool_names[0]}'，请使用`json toolcall`代码块！"
                ui_msg = f"检测到json代码块中的工具调用: {unique_tool_names[0]}"
            else:
                warning_msg = f"警告：你使用了`json`代码块而非`json toolcall`代码块调用了工具{unique_tool_names}，请使用`json toolcall`代码块！"
                ui_msg = f"检测到json代码块中的工具调用: {', '.join(unique_tool_names)}"

            agent.message_processor.add_new_message(RuntimeMessage(warning_msg))
            await self.group_chat.send_if_exists(
                "ui_log", CliRuntimeNotice(level="WARNING", content=ui_msg)
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class RuntimeImitationPlugin(Plugin):
    """阻断deepseek模型模仿runtime输出的插件。"""

    async def after_token_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """检查deepseek是否在模仿runtime输出并阻断。"""
        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility != "deepseek":
            return False

        if matches := re.search(r"^\s*<<([a-z_]+)>>", current_content, re.MULTILINE):
            if matches.group(1) == "agent":
                await agent.interrupt("不要输出<<agent>>这个tag!")
            else:
                await agent.interrupt(f"不要模仿{matches.group(1)}的输出！")
            return True

        if current_content.lstrip().startswith("<tool>{"):
            await agent.interrupt("工具调用的格式是```json toolcall不是XML!")
            return True

        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


class DuplicateFileReadPlugin(Plugin):
    """拦截重复文件读取以优化代理行为。

    重复读取相同文件内容浪费token并减慢任务进度。此插件通过检查已有FileContentMessage来检测重复。
    只检查read_file工具，不检查read_file_with_sed。
    """

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_after_tool_call(self._after_tool_call)

    async def _after_tool_call(
        self,
        agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ) -> Optional[RuntimeMessage]:
        """工具调用后回调，检查是否重复读取文件。"""
        # 只在master_host上拦截
        from linhai.machine_control import MachineControl

        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        if not success:
            return None

        tool_name = tool_call.function_name
        if tool_name != "read_file":
            return None

        filepath = tool_call.function_arguments.get("filepath")
        if not filepath:
            return None

        if isinstance(tool_result, FileContentMessage):
            return await self._handle_read_file(agent, filepath, tool_result)

        return None

    async def _handle_read_file(
        self, agent: "Agent", filepath: str, tool_result: FileContentMessage
    ) -> Optional[RuntimeMessage]:
        """处理read_file工具的重复读取检查。"""
        try:
            absolute_filepath = str(Path(filepath).resolve())
        except (OSError, ValueError):
            return None

        recent_file_messages = []
        for message in reversed(list(agent.message_processor.get_messages())):
            if not isinstance(message, FileContentMessage):
                continue
            try:
                if str(Path(message.filepath).resolve()) == absolute_filepath:
                    recent_file_messages.append(message)
            except (OSError, ValueError):
                # 如果历史消息中的路径无法解析，跳过该消息
                continue

        if recent_file_messages:
            latest_message = recent_file_messages[0]
            if latest_message.content == tool_result.content:
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="INFO",
                        content="模型重复读取相同文件，已阻止",
                    ),
                )
                content = latest_message.content
                reprobj = reprlib.Repr(maxstring=100)

                preview = reprobj.repr(content)
                return RuntimeMessage(
                    f"错误：你已经读取过文件{tool_result.filepath}，内容和上一次完全相同，本条重复内容已自动隐藏。\n"
                    f"文件内容预览：{preview}\n"
                    f"不要重复读取文件拖延时间！你应该立即修改文件而不是继续拖延！"
                )
            return None

        return None


class WrongTimeoutPlugin(Plugin):
    """在Agent使用timeout命令而不使用timeout参数时ban掉run_command工具"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.ban_until = 0

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)

    async def before_tool_call(
        self,
        tool_call: ToolCallMessage,
    ) -> bool:
        """工具调用后回调，检查是否是无用的run_command。"""
        if tool_call.function_name != "run_command":
            return False

        agent = self.group_chat.get_members("agent", Agent)

        if self.ban_until > time.time():
            await agent.interrupt(
                f"错误：因为你的错误行为，当前run_command已被禁用，剩余{self.ban_until-time.time()}s解锁，请反思你的行为！"
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="惩罚：Agent未正确使用timeout参数，已惩罚性禁止使用run_command",
                ),
            )
            return True

        command = tool_call.function_arguments.get("command")
        if not isinstance(command, str) or not command.startswith("timeout "):
            return False

        if tool_call.function_arguments.get("timeout"):
            return False

        self.ban_until = time.time() + 180

        await agent.interrupt(
            "错误：因为你的错误行为，当前run_command已被禁用三分钟，请立即反思你的行为！"
            "你做错的事情是：没有使用timeout参数而是使用timeout命令设置超时，你没发现这一点用都没有吗？"
            "如果你想让一个程序一直运行，你应该使用终端而不是使用timeout！"
            "如果你想让一个程序在超时后退出，你应该使用timeout参数而不是命令！"
        )
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="WARNING",
                content="惩罚：Agent未正确使用timeout参数，已惩罚性禁止使用run_command三分钟",
            ),
        )
        return True


class WrongLinhaiPlugin(Plugin):
    """禁止使用run_command调用linhai"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.ban_until = 0

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)

    async def before_tool_call(
        self,
        tool_call: ToolCallMessage,
    ) -> bool:
        """工具调用后回调，检查是否是无用的run_command。"""
        if tool_call.function_name != "run_command":
            return False

        agent = self.group_chat.get_members("agent", Agent)

        if self.ban_until > time.time():
            await agent.interrupt(
                f"错误：因为你的错误行为，当前run_command已被禁用，剩余{self.ban_until-time.time()}s解锁，请反思你的行为！"
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="惩罚：Agent使用run_command运行linhai，已惩罚性禁止使用run_command",
                ),
            )
            return True

        command = tool_call.function_arguments.get("command")
        if not isinstance(command, str) or " linhai " not in command:
            return False

        self.ban_until = time.time() + 180

        await agent.interrupt(
            "错误：因为你的错误行为，当前run_command已被禁用三分钟，请立即反思你的行为！"
            "你做错的事情是：直接在run_command中使用linhai"
        )
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="WARNING",
                content="惩罚：Agent使用run_command运行linhai，已惩罚性禁止使用run_command三分钟",
            ),
        )
        return True


class UnnecessarySedReadPlugin(Plugin):
    """拦截不必要的sed调用插件。

    在检测到读取"过小文件"或"已读取文件"时警告，超过3次才拦截，使用过read_file就重置计数。
    """

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.warning_count = 0
        self.last_reset_time = time.time()

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_after_tool_call(self._after_tool_call)

    async def _after_tool_call(
        self,
        agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ) -> Optional[RuntimeMessage]:
        """工具调用后回调，检查是否不必要的小块读取。"""

        # 只在master_host上拦截
        from linhai.machine_control import MachineControl

        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        if not success:
            return None

        # 如果使用了read_file，重置警告计数
        if tool_call.function_name == "read_file":
            self.warning_count = 0
            return None

        if tool_call.function_name != "read_file_with_sed":
            return None

        filepath = tool_call.function_arguments.get("filepath")
        if not filepath:
            return None

        # 检查文件是否过小或已读取
        is_small_file = await self._is_small_file(filepath)
        is_already_read = await self._is_already_read(agent, filepath)
        
        if not is_small_file and not is_already_read:
            return None

        # 增加警告计数
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

    async def _is_small_file(self, filepath: str) -> bool:
        """检查文件是否过小（字符数少于15000且行数少于800行）。"""
        return await is_small_file(filepath)

    async def _is_already_read(self, agent: "Agent", filepath: str) -> bool:
        """检查文件是否已被读取（最新FileContentMessage内容与硬盘文件内容相同）。"""
        return await is_already_read(agent, filepath)


class UnnecessaryRunCommandPlugin(Plugin):
    """拦截无用的run_command调用插件。

    在检测到读取“过小文件”或“已读取文件”时警告，超过3次才拦截，使用过read_file就重置计数。
    不区分是否是sed调用，跳过用pipe连接起来的命令，删除判断参数是否是文件路径的逻辑，
    仅通过检测“参数是否是存在的文件路径”判断参数是否是文件路径。
    """

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.warning_count = 0
        self.last_reset_time = time.time()

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_after_tool_call(self._after_tool_call)

    async def _after_tool_call(
        self,
        agent: "Agent",
        tool_call: ToolCallMessage,
        _tool_result: Any,
        success: bool,
    ) -> Optional[RuntimeMessage]:
        """工具调用后回调，检查是否是无用的run_command。"""
        if not success:
            return None

        # 只在master_host上拦截
        from linhai.machine_control import MachineControl

        machine_control = self.group_chat.get_members("machine_control", MachineControl)
        if machine_control.target_machine != "master_host":
            return None

        # 如果使用了read_file，重置警告计数
        if tool_call.function_name == "read_file":
            self.warning_count = 0
            return None

        if tool_call.function_name != "run_command":
            return None

        command = tool_call.function_arguments.get("command")
        if not command or not isinstance(command, str):
            return None

        # 跳过包含管道的命令
        if "|" in command:
            return None

        # 解析命令参数，检查是否有参数是存在的文件路径
        file_args = self._extract_file_args(command)
        if not file_args:
            return None

        # 检查每个文件参数是否过小或已读取
        has_small_or_read_file = False
        for file_arg in file_args:
            if await is_small_file(file_arg) or await is_already_read(agent, file_arg):
                has_small_or_read_file = True
                break

        if not has_small_or_read_file:
            return None

        # 增加警告计数
        self.warning_count += 1
        
        if self.warning_count >= 3:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="模型多次使用命令查看已读取文件，已阻止",
                ),
            )
            return RuntimeMessage(
                "错误：不使用read_file直接读取文件而是滥用命令查看已读取文件\n"
                "警告：本插件会一直阻止你重复读取文件，直到你开始改代码为止！\n"
                "建议：如果需要查看文件内容，使用read_file读取整个文件！"
            )
        else:
            # 只警告，不拦截
            return RuntimeMessage(
                f"警告：检测到使用命令查看已读取文件（第{self.warning_count}次警告）。建议使用read_file读取整个文件。"
            )

    def _extract_file_args(self, command: str) -> list[str]:
        """从命令中提取可能的文件参数。"""
        # 简单的参数解析：按空格分割，跳过命令名和以"-"开头的选项
        parts = command.strip().split()
        if not parts:
            return []
        
        file_args = []
        # 跳过命令名
        for i in range(1, len(parts)):
            arg = parts[i]
            # 跳过以"-"开头的选项
            if arg.startswith("-"):
                continue
            # 检查是否为存在的文件路径
            if self._is_existing_file(arg):
                file_args.append(arg)
        
        return file_args
    
    def _is_existing_file(self, path_str: str) -> bool:
        """检查路径是否为存在的文件。"""
        try:
            path = Path(path_str)
            return path.is_file()
        except (OSError, ValueError):
            return False


def get_children(node: bashlex.ast.node) -> list[bashlex.ast.node]:
    """获取节点的子节点列表，不使用hasattr。"""
    node_kind = node.kind  # type: ignore[attr-defined]
    if node_kind == "compound":
        return node.list  # type: ignore[attr-defined]
    elif node_kind in ["command", "pipeline", "list"]:
        return node.parts  # type: ignore[attr-defined]
    else:
        return []


def traverse_ast(
    node: bashlex.ast.node, in_pipeline: bool, forbidden_commands: set[str]
) -> bool:
    """遍历AST节点，检查是否包含需要拦截的命令。"""
    node_kind = node.kind  # type: ignore[attr-defined]

    if node_kind in ["pipeline", "list", "compound"]:
        for child in get_children(node):
            child_in_pipeline = in_pipeline or (node_kind == "pipeline")
            if traverse_ast(child, child_in_pipeline, forbidden_commands):
                return True
        return False

    if node_kind == "command":
        cmd_name = None
        has_redirect = False

        for part in get_children(node):
            if part.kind == "redirect":  # type: ignore[attr-defined]
                has_redirect = True
                continue
            if cmd_name is None and part.kind == "word":  # type: ignore[attr-defined]
                cmd_name = part.word  # type: ignore[attr-defined]

        if cmd_name in forbidden_commands and not has_redirect and not in_pipeline:
            return True

        for child in get_children(node):
            if traverse_ast(child, in_pipeline, forbidden_commands):
                return True
        return False

    for child in get_children(node):
        if traverse_ast(child, in_pipeline, forbidden_commands):
            return True
    return False


def should_block_command_with_files(command: str, read_files: set[Path]) -> bool:
    """
    判断一个shell命令是否应该被拦截，检查是否访问已读取的文件。

    规则：
    - 命令是禁止的命令之一（grep, head, tail, cat, sed）
    - 命令不在管道中且没有重定向
    - 命令访问了已读取的文件

    返回True表示应该拦截，False表示允许。
    """
    if not command.strip():
        return False

    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError:
        return False

    return traverse_ast_with_files(parts, False, read_files)


def traverse_ast_with_files(
    nodes: list[bashlex.ast.node], in_pipeline: bool, read_files: set[Path]
) -> bool:
    """遍历AST节点，检查是否包含访问已读取文件的禁止命令。"""
    for node in nodes:
        if _traverse_ast_with_files_node(node, in_pipeline, read_files):
            return True
    return False


def _traverse_ast_with_files_node(
    node: bashlex.ast.node, in_pipeline: bool, read_files: set[Path]
) -> bool:
    """遍历单个AST节点，检查是否包含访问已读取文件的禁止命令。"""
    node_kind = node.kind  # type: ignore[attr-defined]

    if node_kind in ["pipeline", "list", "compound"]:
        for child in get_children(node):
            child_in_pipeline = in_pipeline or (node_kind == "pipeline")
            if _traverse_ast_with_files_node(child, child_in_pipeline, read_files):
                return True
        return False

    if node_kind == "command":
        return _process_command_node(node, in_pipeline, read_files)

    for child in get_children(node):
        if _traverse_ast_with_files_node(child, in_pipeline, read_files):
            return True
    return False


def _process_command_node(
    node: bashlex.ast.node, in_pipeline: bool, read_files: set[Path]
) -> bool:
    """处理命令节点，检查是否访问已读取文件。"""
    cmd_name, has_redirect, accesses_read_file = _analyze_command_parts(
        node, read_files
    )

    if (
        cmd_name in {"grep", "head", "tail", "cat", "sed", "awk", "rg"}
        and not has_redirect
        and not in_pipeline
        and accesses_read_file
    ):
        return True

    for child in get_children(node):
        if _traverse_ast_with_files_node(child, in_pipeline, read_files):
            return True
    return False


def _analyze_command_parts(
    node: bashlex.ast.node, read_files: set[Path]
) -> tuple[Optional[str], bool, bool]:
    """分析命令节点各部分，提取命令名、重定向状态和文件访问状态。"""
    cmd_name: Optional[str] = None
    has_redirect = False
    accesses_read_file = False
    expecting_option_value = False

    for part in get_children(node):
        if part.kind == "redirect":  # type: ignore[attr-defined]
            has_redirect = True
            continue

        if part.kind != "word":  # type: ignore[attr-defined]
            continue

        word = part.word  # type: ignore[attr-defined]

        if cmd_name is None:
            cmd_name = word
            continue

        if word.startswith("-"):
            # 检查是否为数字参数，如 -10, -n10 等
            # 如果参数是纯数字（去掉开头的减号后全是数字），则不是需要值的选项
            suffix = word.lstrip("-")
            is_numeric_arg = suffix.isdigit()
            expecting_option_value = "=" not in word and not is_numeric_arg
            continue

        if expecting_option_value:
            expecting_option_value = False
            continue

        if _is_read_file(word, read_files):
            accesses_read_file = True

    return cmd_name, has_redirect, accesses_read_file


def _is_read_file(word: str, read_files: set[Path]) -> bool:
    """检查单词是否为已读取的文件路径。"""
    try:
        path = Path(word).resolve()
        return path in read_files
    except (OSError, ValueError):
        return False


async def is_small_file(filepath: str) -> bool:
    """检查文件是否过小（字符数少于15000且行数少于800行）。"""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
            char_count = len(content)
            # 估算行数：计算换行符数量
            line_count = content.count(b"\n")
            return char_count < 15000 and line_count < 800
    except (FileNotFoundError, PermissionError, OSError):
        return False


async def is_already_read(agent: "Agent", filepath: str) -> bool:
    """检查文件是否已被读取（最新FileContentMessage内容与硬盘文件内容相同）。"""
    try:
        abs_path = Path(filepath).resolve()
        # 读取硬盘文件内容
        with open(abs_path, "rb") as f:
            disk_content = f.read().decode("utf-8", errors="ignore")
    except (OSError, ValueError, UnicodeDecodeError):
        return False

    # 查找相同文件路径的最新FileContentMessage
    latest_message = None
    for msg in reversed(list(agent.message_processor.get_messages())):
        if isinstance(msg, FileContentMessage):
            try:
                if Path(msg.filepath).resolve() == abs_path:
                    latest_message = msg
                    break
            except (OSError, ValueError):
                continue

    if latest_message and latest_message.content == disk_content:
        return True
    return False
