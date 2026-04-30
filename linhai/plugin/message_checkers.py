"""消息生成检查插件。"""

import re
import time

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Literal, Union

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.state_machine import AgentStateMachine
from linhai.agent.messages import (
    RuntimeMessage,
    WAITING_USER_MARKER,
    SpoofedReasoningMessage,
)
from linhai.registry import Registry
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.base import Answer, AssistantMessage, Message
from linhai.utils.common import UiNotice
from linhai.utils.i18n import t

from .helpers import JsonValue

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, registry: Registry):
        self.registry = registry

    @abstractmethod
    def register(self, lifecycle: "Lifecycle") -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(self, parsed_answer, tool_calls):
        """检查等待用户标记的位置和工具调用冲突。"""
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)
        if not agent.get_current_model().get_custom_toolcall_format():
            return
        has_waiting_marker = WAITING_USER_MARKER in full_response

        if tool_calls and has_waiting_marker:
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                    f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING", content="已警告agent：工具调用和等待用户冲突"
                ),
            )
            return
        state_machine = self.registry.get_member_typechecked(
            "state_machine", AgentStateMachine
        )
        if (
            state_machine.state == "working"
            and not tool_calls
            and not has_waiting_marker
            and full_response.strip()
        ):
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"错误 - 垃圾消息：既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用）。"
                    "runtime不知道你是需要暂停等待还是需要继续调用工具，因此让你继续生成消息，之前的消息内容已经发送给用户。"
                    f"如果你不再需要调用任何工具（任务完成/无法完成），需要直接回复用户：使用{WAITING_USER_MARKER!r}等待用户回答，并保证:"
                    "1. 你不完全重复回答 - 因为用户已经看到了，重复回答会导致用户看到两条消息。"
                    f"2. 你正确在结尾加上{WAITING_USER_MARKER!r} - 否则runtime仍然不知道你是否需要等待用户。"
                    "3. 这条回复应该明显短于之前的回复 - 否则用户会看到两条长消息"
                    f"如果需要调用工具：必须继续输出工具调用且不应同时使用{WAITING_USER_MARKER!r}"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="已警告agent：既没有调用工具也没有等待用户",
                ),
            )
            return

        if has_waiting_marker:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                await agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                state_machine.transition_to_waiting_user()

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class WrongEndPlugin(Plugin):
    """禁止输出end of sentence的plugin"""

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls,
    ):
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)
        regex_result = re.search(r"<｜end▁of▁[a-z]+｜>", full_response)
        if regex_result:
            await agent.message_processor.add_new_message(
                RuntimeMessage(f"警告: 输出了错误的token: {regex_result!r}")
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class EndThinkPlugin(Plugin):
    """检查输出中是否有只有'</think>'的行并打断agent。"""

    async def after_token_generation(
        self, agent: "Agent", _answer: Answer, current_content: str
    ):
        """检查是否有一行只有'</think>'。"""
        lines = current_content.split("\n")
        for line in lines:
            if line.strip() == "</think>":
                await agent.agent_llm.interrupt(
                    "错误：检测到只有'</think>'的行，你将两条消息合并成了一条发送！请依次发送每条消息！",
                    "Agent消息合并错误，已纠正",
                )
                return True
        return False

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.after_token_generation.register(self.after_token_generation)


class VolcanoDeepseekFixPlugin(Plugin):
    """处理火山平台deepseek异常输出的插件。"""

    ABNORMAL_MARKER = "</think>```json toolcall"
    CONTEXT_CHARS = 50
    NORMAL_MARKER = "```json toolcall"

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: list,
    ) -> None:
        """在消息生成后检查并提醒异常标记。"""
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)

        positions = [
            m.start()
            for m in re.finditer(re.escape(self.ABNORMAL_MARKER), full_response)
        ]

        if not positions:
            return

        contexts = []
        for pos in positions:
            context_start = max(0, pos - self.CONTEXT_CHARS)
            context_end = min(
                len(full_response), pos + len(self.ABNORMAL_MARKER) + self.CONTEXT_CHARS
            )
            context = full_response[context_start:context_end]
            if context_start > 0:
                context = "..." + context
            if context_end < len(full_response):
                context = context + "..."
            contexts.append(context)

        warning_msg = (
            f"警告：检测到火山平台 deepseek 的异常输出标记{self.ABNORMAL_MARKER}'。\n"
            f"正确的工具调用格式应该是'```json toolcall'而不是{self.ABNORMAL_MARKER}'。\n"
            f"请修正输出格式。\n\n"
            f"异常位置附近的内容:\n"
            + "\n".join(
                f"[位置{i}]\n{context}" for i, context in enumerate(contexts, 1)
            )
            + "尝试在</think>和工具调用之间加上一行内容，如:\n\n</think>我将正确调用工具\n\n```json toolcall\n"
        )

        await agent.message_processor.add_new_message(RuntimeMessage(warning_msg))

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="WARNING",
                content=f"检测到火山平台 deepseek 异常输出标记：共{len(positions)}处，已提醒 agent 并显示上下文",
            ),
        )

    def register(self, lifecycle: "Lifecycle") -> None:
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class OnlyReasoningPlugin(Plugin):
    """针对deepseek v3.2检测是否只思考不输出"""

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: List[Dict[str, JsonValue]],
    ):
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)
        model = agent.get_current_model()

        if model.get_compatibility() != "deepseek":
            return

        reasoning_content = parsed_answer._answer.get_reasoning_message()

        if reasoning_content and not full_response.strip():
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    t(
                        {
                            "zh_CN": "检测到在思考后没有输出任何内容而是在</thinking>标签前就输出了工具调用等，应该在</thinking>标签后输出实际内容",
                            "en": "Detected no output after thinking, with tool calls before </thinking> tag. Actual content should be output after the </thinking> tag",
                        }
                    )
                ),
                source="only_reasoning",
                sort_value=0,
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="WARNING", content="模型只思考不输出，已提醒模型"),
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="only_reasoning", sort_value=0
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class PreviousReasoningPlugin(Plugin):
    """提供agent最近思考内容的插件。"""

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: List[Dict[str, JsonValue]],
    ):
        agent = self.registry.get_member_typechecked("agent", Agent)

        msgs = [
            msg.reasoning_message
            for msg in agent.message_processor.get_messages()
            if isinstance(msg, AssistantMessage) and msg.reasoning_message
        ]
        if msgs:
            previous_reasoning_msg = SpoofedReasoningMessage(msgs[-6:])
            agent.message_processor.update_notification_message(
                previous_reasoning_msg, source="previous_reasoning", sort_value=1000
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="previous_reasoning", sort_value=1000
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class JsonCodeBlockPlugin(Plugin):
    """检测agent误用`json`而非`json toolcall`代码块的插件。"""

    async def after_message_generation(self, parsed_answer, _tool_calls):
        """检查是否有json代码块包含有效的工具调用。"""
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)

        if not agent.get_current_model().get_custom_toolcall_format():
            return

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

            await agent.message_processor.add_new_message(RuntimeMessage(warning_msg))
            await self.registry.send_if_exists(
                "ui_log", UiNotice(level="WARNING", content=ui_msg)
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class KimiK25ToolCallPlugin(Plugin):
    """处理火山平台kimi k2.5特殊工具调用格式的插件。"""

    TIME_WINDOW_SECONDS = 60

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._last_error_format_time: float | None = None

    async def after_token_generation(
        self,
        agent: "Agent",
        _answer: Answer,
        current_content: str,
    ) -> bool:
        """在token生成后检查是否需要打断agent。"""
        if not agent.get_current_model().get_custom_toolcall_format():
            return False

        if self._last_error_format_time is None:
            return False

        if time.time() - self._last_error_format_time > self.TIME_WINDOW_SECONDS:
            return False

        first_line, _, _ = current_content.partition("\n")
        first_line = first_line.strip()
        if "<|tool_call_begin|>" in first_line or "<|tool_call_end|>" in first_line:
            await agent.agent_llm.interrupt(
                "错误：检测到kimi k2.5特殊工具调用格式。请使用正确的`json toolcall`代码块格式。",
                "Agent使用了错误的工具调用格式，已打断",
            )
            return True

        return False

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: list[dict],
    ):
        full_response = parsed_answer.get_message().get_content() or ""
        if not full_response:
            return

        agent = self.registry.get_member_typechecked("agent", Agent)
        if not agent.get_current_model().get_custom_toolcall_format():
            return

        has_kimi_marker = "<|tool_call_begin|>" in full_response
        has_correct_format = "```json toolcall" in full_response

        if has_kimi_marker and not has_correct_format:
            self._last_error_format_time = time.time()
            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：检测到不支持的kimi k2.5特殊工具调用格式`<|tool_call_begin|>`，"
                    "但没有正确的`json toolcall`代码块格式。\n"
                    "正确的工具调用格式是使用`json toolcall`代码块，例如：\n"
                    "```json toolcall\n"
                    '{"name": "tool_name", "arguments": {...}}\n'
                    "```"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到kimi k2.5特殊工具调用格式，已提醒模型",
                ),
            )

        if (
            "```<|tool_call_end|>" in full_response
            or "}<|tool_call_end|>" in full_response
        ):
            self._last_error_format_time = time.time()
            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：检测到混用json toolcall和kimi k2.5的特殊工具调用格式`<|tool_call_end|>`。"
                    "这可能会导致markdown解析错误。"
                    "正确的工具调用格式是**只**使用`json toolcall`代码块，例如：\n"
                    "```json toolcall\n"
                    '{"name": "tool_name", "arguments": {...}}\n'
                    "```"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到kimi k2.5特殊工具调用格式，已提醒模型",
                ),
            )

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.after_token_generation.register(self.after_token_generation)
        lifecycle.after_message_generation.register(self.after_message_generation)


class MinimaxToolCallPlugin(Plugin):
    """处理minimax特殊工具调用格式的插件。"""

    TIME_WINDOW_SECONDS = 60

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._last_error_format_time: float | None = None

    async def after_token_generation(
        self,
        agent: "Agent",
        _answer: Answer,
        current_content: str,
    ) -> bool:
        if not agent.get_current_model().get_custom_toolcall_format():
            return False

        if self._last_error_format_time is None:
            return False

        if time.time() - self._last_error_format_time > self.TIME_WINDOW_SECONDS:
            return False

        first_line, _, _ = current_content.partition("\n")
        first_line = first_line.strip()
        if "<minimax:tool_call>" in first_line:
            await agent.agent_llm.interrupt(
                "错误：检测到minimax特殊工具调用格式。请使用正确的`json toolcall`代码块格式。",
                "Agent使用了错误的工具调用格式，已打断",
            )
            return True

        return False

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: list[dict],
    ):
        full_response = parsed_answer.get_message().get_content() or ""
        if not full_response:
            return

        agent = self.registry.get_member_typechecked("agent", Agent)
        if not agent.get_current_model().get_custom_toolcall_format():
            return

        has_minimax_marker = "<minimax:tool_call>" in full_response
        has_correct_format = "```json toolcall" in full_response

        lines = full_response.split("\n")
        has_minimax_m25_error = lines and lines[0].strip() == "[TOOL_CALL]"

        if has_minimax_m25_error:
            self._last_error_format_time = time.time()
            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：检测到minimax m2.5的错误工具调用格式`[TOOL_CALL]`。"
                    "正确的工具调用格式是使用`json toolcall`代码块，例如：\n"
                    "```json toolcall\n"
                    '{"name": "tool_name", "arguments": {...}}\n'
                    "```"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到minimax m2.5错误工具调用格式，已提醒模型",
                ),
            )

        if has_minimax_marker and not has_correct_format:
            self._last_error_format_time = time.time()
            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：检测到不支持的minimax特殊工具调用格式`<minimax:tool_call>`，"
                    "但没有正确的`json toolcall`代码块格式。\n"
                    "正确的工具调用格式是使用`json toolcall`代码块，例如：\n"
                    "```json toolcall\n"
                    '{"name": "tool_name", "arguments": {...}}\n'
                    "```"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到minimax特殊工具调用格式，已提醒模型",
                ),
            )

        if (
            "```<minimax:tool_call>" in full_response
            or "}<minimax:tool_call>" in full_response
        ):
            self._last_error_format_time = time.time()
            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：检测到混用json toolcall和minimax的特殊工具调用格式`<minimax:tool_call>`。"
                    "这可能会导致markdown解析错误。"
                    "正确的工具调用格式是**只**使用`json toolcall`代码块，例如：\n"
                    "```json toolcall\n"
                    '{"name": "tool_name", "arguments": {...}}\n'
                    "```"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到minimax特殊工具调用格式，已提醒模型",
                ),
            )

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.after_token_generation.register(self.after_token_generation)
        lifecycle.after_message_generation.register(self.after_message_generation)


class RuntimeImitationPlugin(Plugin):
    """阻断deepseek等模型模仿runtime输出的插件。"""

    async def after_token_generation(
        self,
        agent: "Agent",
        _answer: Answer,
        current_content: str,
    ):
        """检查deepseek等是否在模仿runtime输出并阻断。"""

        if not agent.get_current_model().get_custom_toolcall_format():
            return False

        if matches := re.search(r"^\s*<<([a-z_]+)>>", current_content, re.MULTILINE):
            if matches.group(1) == "agent":
                await agent.agent_llm.interrupt(
                    "不要输出<<agent>>这个tag!", "Agent输出了无效标签，已纠正"
                )
            else:
                await agent.agent_llm.interrupt(
                    f"不要模仿{matches.group(1)}的输出！",
                    "Agent尝试模仿其他输出格式，已纠正",
                )
            return True

        if current_content.lstrip().startswith("<tool>{"):
            await agent.agent_llm.interrupt(
                "工具调用的格式是```json toolcall不是XML!",
                "Agent使用了错误的工具调用格式，已纠正",
            )
            return True

        return False

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.after_token_generation.register(self.after_token_generation)


class GlmToolCallPlugin(Plugin):
    """处理GLM错误工具调用格式的插件。"""

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: list,
    ):
        """在消息生成后检查GLM是否错误使用了<tool_call>格式。"""
        agent = self.registry.get_member_typechecked("agent", Agent)
        model = agent.get_current_model()

        if model.get_compatibility() != "glm":
            return

        if not model.get_custom_toolcall_format():
            return
        full_response = parsed_answer.get_message().get_content() or ""

        if full_response.lstrip().startswith("<tool_call>"):
            warning_msg = (
                "警告：检测到无效的GLM工具调用格式<tool_call>，你是不是搞错工具输出格式了？\n"
                "正确的工具调用格式是使用`json toolcall`代码块，例如：\n"
                "```json toolcall\n"
                '{"name": "tool_name", "arguments": {...}}\n'
                "```"
            )
            await agent.message_processor.add_new_message(RuntimeMessage(warning_msg))
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="检测到GLM错误工具调用格式，已提醒模型",
                ),
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class MisplacedToolCallPlugin(Plugin):
    """检测```json toolcall不在行首的插件。"""

    MARKER = "```json toolcall"

    async def after_message_generation(
        self,
        parsed_answer,
        _tool_calls: list,
    ):
        full_response = parsed_answer.get_message().get_content() or ""
        agent = self.registry.get_member_typechecked("agent", Agent)

        misplaced_lines: list[str] = []
        for line in full_response.split("\n"):
            if self.MARKER in line and not line.lstrip().startswith(self.MARKER):
                misplaced_lines.append(line.strip())

        if not misplaced_lines:
            return

        warning_msg = (
            "警告：检测到```json toolcall不在一行的开头。"
            "工具调用的```json toolcall必须在行首，前面不能有其他文字。\n"
            "错误示例：一些文字```json toolcall\n"
            "正确示例：\n```json toolcall\n"
        )
        await agent.message_processor.add_new_message(RuntimeMessage(warning_msg))
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="WARNING",
                content=f"检测到```json toolcall不在行首：共{len(misplaced_lines)}处，已提醒agent",
            ),
        )

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.after_message_generation.register(self.after_message_generation)


class WaitingUserReminderPlugin(Plugin):

    REMINDER_THRESHOLD = 10
    REMINDER_MESSAGE = (
        f"注意：你应该在消息的末尾使用{WAITING_USER_MARKER!r}以停下等待用户，"
        "除非你还需要继续调用工具"
    )

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self._message_count = 0

    async def before_message_generation(self) -> None:
        agent = self.registry.members.get("agent")
        if agent is None:
            return

        if self._message_count < self.REMINDER_THRESHOLD:
            agent.message_processor.update_notification_message(
                RuntimeMessage(self.REMINDER_MESSAGE),
                source="waiting_user_reminder",
                sort_value=800,
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="waiting_user_reminder", sort_value=800
            )

    async def after_message_generation(self, parsed_answer, tool_calls):
        self._message_count += 1

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.before_message_generation.register(self.before_message_generation)
        lifecycle.after_message_generation.register(self.after_message_generation)


class GlmInsultMaskPlugin(Plugin):
    """GLM脏话检查插件，屏蔽脏话为拼音。"""

    INSULTS = {
        "傻逼": "shabi",
        "垃圾": "laji",
        "弱智": "ruozhi",
        "脑残": "naocan",
    }

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: "Message | None",
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """在工具调用后检查结果是否包含脏话。"""
        if status == "skipped":
            return None

        if message is None:
            return None

        result_content = message.get_content()
        if result_content is None:
            return None

        agent = self.registry.get_member_typechecked("agent", Agent)
        model = agent.get_current_model()
        if model.get_compatibility() != "glm":
            return None

        has_insult = False
        masked_content = result_content

        for insult, pinyin in self.INSULTS.items():
            if insult in masked_content:
                has_insult = True
                masked_content = masked_content.replace(insult, pinyin)

        if not has_insult:
            return None

        warning_msg = (
            "<<insult-mask>><<message>>你是GLM，当前工具结果中包含脏话，"
            "为了符合API TOS、保证正常运行，脏话已屏蔽为拼音<<message>><<masked>>"
            f"{masked_content}<<masked>><<insult-mask>>"
        )
        return RuntimeMessage(warning_msg)

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_toolcall回调。"""
        lifecycle.after_toolcall.register(self.after_toolcall)
