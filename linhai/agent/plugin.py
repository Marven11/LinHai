"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod

from pathlib import Path
import re
import time
import bashlex
import bashlex.ast
import bashlex.errors
from typing import Any, Dict, List, Optional, TypeAlias, Union

from linhai.agent import Agent
import linhai.agent as linhai_agent
from linhai.agent.base import GlobalMemory, PathMemory, FileContentMessage
from linhai.group_chat import GroupChat
from linhai.markdown_parser import extract_tool_calls, extract_tool_calls_with_errors
from .base import RuntimeMessage, WAITING_USER_MARKER, PreviousReasoningMessage
from ..llm import Answer, AssistantMessage, OpenAi, ToolCallMessage
from ..utils import CliRuntimeNotice
from linhai.tool.base import ToolResultMessage


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
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                        f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                    )
                )
                return
            if agent.state == "working" and not tool_calls and not has_waiting_marker:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用），"
                        f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                    )
                )
                return

        if has_waiting_marker:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                agent.message_processor.append_message(
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
            agent.message_processor.append_message(
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

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前检查目录是否更改。"""
        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility not in [
            "minimax",
            "glm",
        ]:
            return

        has_previous_agent_message = any(
            isinstance(msg, AssistantMessage)
            for msg in agent.message_processor.get_messages()
        )

        if not has_previous_agent_message:
            agent.message_processor.append_message(
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
            agent.message_processor.append_message(
                RuntimeMessage("你现在是GLM，必须打开思考模式，仔细思考！")
            )

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

        if current_content.count("```json toolcall") > self.MAX_TOOLCALL_COUNT:
            extra_message = ""
            if self.speeding_counter:
                extra_message = (
                    "从刚刚开始就一直在调用大量工具，你疯了？？？？"
                    + "？！？！" * self.speeding_counter
                )
            agent.message_processor.append_message(
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
        """注册before_message_generation和after_token_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
        lifecycle.register_after_token_generation(self.after_token_generation)


class SlowStartPlugin(Plugin):
    """防止agent在一开始就调用大量工具的插件"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.enabled = True

    async def after_token_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        if not self.enabled:
            return

        if current_content.count("```json toolcall") > 5:
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
                agent.message_processor.append_message(
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

        enable_directory_change_detection = agent.context.get(
            "enable_directory_change_detection", False
        )
        if not enable_directory_change_detection:
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
                    agent.message_processor.append_message(PathMemory(filepath))

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
                    ),
                    source="single_tool_call_reminder",
                )
            else:
                agent.message_processor.update_appending_message(
                    None, source="single_tool_call_reminder"
                )
        else:
            self.single_tool_call_count = 0
            agent.message_processor.update_appending_message(
                None, source="single_tool_call_reminder"
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
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING", content="模型只思考不输出，已提醒模型"
                ),
            )
        else:
            agent.message_processor.update_appending_message(
                None, source="only_reasoning"
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
            previous_reasoning_msg = PreviousReasoningMessage(msgs[-3:])
            agent.message_processor.update_appending_message(
                previous_reasoning_msg, source="previous_reasoning"
            )
        else:
            agent.message_processor.update_appending_message(
                None, source="previous_reasoning"
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

        agent.message_processor.append_message(RuntimeMessage(agent_warning_message))
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="WARNING", content=ui_warning_message),
        )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class PreventToolOutputPlugin(Plugin):
    """防止agent错误输出工具调用内容的插件。

    当agent的第一个回复中有一行的开头是`**tool**`时打断agent，
    并提示不要输出工具调用的内容。
    """

    async def after_token_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        agent = self.group_chat.get_members("agent", Agent)

        has_previous_agent_message = any(
            isinstance(msg, AssistantMessage)
            for msg in agent.message_processor.get_messages()
        )

        if not has_previous_agent_message:

            lines = current_content.split("\n")
            for line in lines:
                if line.strip().startswith("**tool**"):
                    agent.message_processor.append_message(
                        RuntimeMessage(
                            "错误：请不要输出工具调用的内容！"
                            "工具调用内容（如`**tool**`）是系统内部使用的标签，"
                            "你不应该直接输出这些内容。"
                        )
                    )
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING", content="LLM错误输出了**tool**，已截断"
                        ),
                    )
                    answer.truncate()
                    return False

        return False

    def register(self, lifecycle):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


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

            agent.message_processor.append_message(RuntimeMessage(warning_msg))
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

        if matches := re.match("^<<([a-z_]+)>>", current_content):
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
    """重复文件读取拦截插件，仅拦截重复读取相同文件内容。

    实现TODO.md中的要求：重复读取同一个文件而且文件内容完全相同则拦截。
    通过查看agent的message是否有相同的FileContentMessage实现。
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
        if not success or tool_call.function_name != "read_file":
            return None

        if not isinstance(tool_result, FileContentMessage):
            return None

        same_file_messages = [
            message
            for message in agent.message_processor.get_messages()
            if isinstance(message, FileContentMessage)
            and message.filepath == tool_result.filepath
        ]

        if len(same_file_messages) >= 1 and same_file_messages[-1] == tool_result:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content="模型重复读取相同文件，已阻止",
                ),
            )
            return RuntimeMessage(
                f"错误：你已经读取过文件{tool_result.filepath}，内容和上一次完全相同，本条重复内容已自动隐藏。"
                "不要重复读取文件拖延时间！你应该立即修改文件而不是继续拖延！"
            )

        return None


class UnnecessarySedReadPlugin(Plugin):
    """拦截不必要的sed调用插件。

    判断规则 - 在一分钟内出现两次读取同一个文件的工具调用：
        - 对应文件行数少于1600行
        - 使用run_sed_expression
        - 工具返回结果小于10000个字符
    """

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.unnecessary_history: Dict[str, float] = {}

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_after_tool_call(self._after_tool_call)

    async def _after_tool_call(
        self,
        _agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ) -> Optional[RuntimeMessage]:
        """工具调用后回调，检查是否不必要的小块读取。"""

        if not success or tool_call.function_name != "run_sed_expression":
            return None

        filepath = tool_call.function_arguments.get("filepath")
        if not filepath:
            return None

        if (
            not isinstance(tool_result, ToolResultMessage)
            or len(tool_result.content) >= 10000
        ):
            return None

        path = Path(filepath)
        if not path.is_file():
            return None

        line_count = await self._get_file_line_count(filepath)
        if line_count is None or line_count >= 1600:
            return None

        last_history = self.unnecessary_history.get(filepath)
        self.unnecessary_history[filepath] = time.time()

        if last_history and self.unnecessary_history[filepath] - last_history < 60:
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content="模型多次小块读取代码文件，已阻止",
                ),
            )
            return RuntimeMessage(
                "错误：一分钟内多次小块读取代码文件\n"
                "违反：优先使用read_file的要求\n"
                "后果：难以理解文件内容、生成多条消息导致重复计费\n"
                "建议：优先带上行号读取整个文件"
            )
        return None

    async def _get_file_line_count(self, filepath: str) -> Optional[int]:
        """获取原始文件的完整行数。使用高效纯Python实现，确保跨平台兼容性。"""
        try:
            with open(filepath, "rb") as f:
                return f.read(32 * 1024).count(b"\n")
        except (FileNotFoundError, PermissionError, OSError):
            return None


class UnnecessaryRunCommandPlugin(Plugin):
    """拦截无用的run_command调用插件。

    禁止以下情况：
    - 直接使用sed命令查看单个文件（提示：“禁止直接使用sed命令查看文件！”）
    - 禁止使用grep, head, tail, cat, sed查看已经读取了的文件
    - 例外：使用`|`或者`>`重定向，有时LLM需要提取文件的其他内容。

    实现：
    1. 跟踪agent已经通过read_file读取的文件
    2. 解析run_command命令，检查是否是禁止的命令
    3. 检查命令是否访问已读取的文件且不在管道/重定向中
    """

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
        if not success or tool_call.function_name != "run_command":
            return None

        command = tool_call.function_arguments.get("command")
        if not command or not isinstance(command, str):
            return None

        read_files = self._get_read_files(agent)
        if not read_files:
            if should_block_command_simple(command):
                return self._generate_warning_message(command)
            return None

        if should_block_command_with_files(command, read_files):
            return self._generate_warning_message(command)

        return None

    def _get_read_files(self, agent: "Agent") -> set[Path]:
        """获取agent已经读取的文件路径集合（绝对路径）。"""
        read_files = set()
        for msg in agent.message_processor.get_messages():
            if isinstance(msg, FileContentMessage):
                try:
                    path = Path(msg.filepath).resolve()
                    read_files.add(path)
                except (OSError, ValueError):
                    continue
        return read_files

    def _generate_warning_message(self, command: str) -> RuntimeMessage:
        """生成警告消息。"""
        forbidden_commands = {"grep", "head", "tail", "cat", "sed"}
        cmd_name = None
        try:
            parts = bashlex.parse(command)
            for ast_node in parts:
                cmd_name = self._extract_command_name(ast_node, forbidden_commands)
                if cmd_name:
                    break
        except bashlex.errors.ParsingError:
            cmd_name = "unknown"

        if cmd_name == "sed":
            return RuntimeMessage("禁止直接使用sed命令查看文件！")
        else:
            return RuntimeMessage(
                f"禁止使用{cmd_name}命令直接查看文件！"
                "如果确实需要提取文件内容，请使用管道或重定向。"
            )

    def _extract_command_name(
        self, node: bashlex.ast.node, forbidden_commands: set[str]
    ) -> Optional[str]:
        """从AST节点中提取命令名，如果命令名在禁止列表中则返回。"""
        if node.kind == "command":  # type: ignore[attr-defined]
            for part in get_children(node):
                if part.kind == "word":  # type: ignore[attr-defined]
                    word = part.word  # type: ignore[attr-defined]
                    # 处理带路径的命令（如/bin/cat）和简单的命令名
                    cmd_name = word.split("/")[-1]  # 获取最后一个部分
                    if cmd_name in forbidden_commands:
                        return cmd_name
        # 递归检查子节点
        for child in get_children(node):
            result = self._extract_command_name(child, forbidden_commands)
            if result:
                return result
        return None


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

    # 处理容器节点
    if node_kind in ["pipeline", "list", "compound"]:
        for child in get_children(node):
            # 对于管道节点，子节点在管道中
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


def should_block_command_simple(command: str) -> bool:
    """
    简单判断一个shell命令是否应该被拦截（不检查文件访问）。

    规则：
    - 命令是单个命令（不在管道中且没有重定向）
    - 命令名是以下之一：grep, head, tail, cat, sed
    - 例外：如果命令在管道中或含有重定向，则允许

    返回True表示应该拦截，False表示允许。
    """
    if not command.strip():
        return False

    try:
        parts = bashlex.parse(command)
    except bashlex.errors.ParsingError:
        return False

    # 禁止的命令列表
    forbidden_commands = {"grep", "head", "tail", "cat", "sed"}

    for ast_node in parts:
        if traverse_ast(ast_node, False, forbidden_commands):
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

    # 检查命令是否访问已读取的文件
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
        cmd_name in {"grep", "head", "tail", "cat", "sed"}
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
            expecting_option_value = "=" not in word
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
