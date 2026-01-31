"""消息生成检查插件。"""

import re

from abc import ABC, abstractmethod
from typing import Dict, List, Union

from linhai.agent import Agent
from linhai.agent.base import GlobalMemory, PathMemory, FileContentMessage, RuntimeMessage, WAITING_USER_MARKER, PreviousReasoningMessage, SpoofedReasoningMessage
from linhai.group_chat import GroupChat
from linhai.markdown_parser import extract_tool_calls, extract_tool_calls_with_errors
from linhai.llm import Answer, AssistantMessage, OpenAi, ToolCallMessage, UserMessage
from linhai.utils import CliRuntimeNotice
from linhai.tool.base import ToolResultSuccess, ToolResultFailed

from .helpers import JsonValue


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
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content="已警告agent：工具调用和等待用户冲突"
                    ),
                )
                return
            if (
                agent.state == "working"
                and not tool_calls
                and not has_waiting_marker
                and full_response.strip()
            ):
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"错误 - 垃圾消息：既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用）。"
                        f"如果你不再需要调用任何工具（任务完成/无法完成），需要直接回复用户：必须使用{WAITING_USER_MARKER!r}等待用户回答"
                        "如果需要调用工具：必须输出工具调用"
                    )
                )
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content="已警告agent：既没有调用工具也没有等待用户",
                    ),
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
        regex_result = re.search(r"<｜end▁of▁[a-z]+｜>", full_response)
        if regex_result:
            agent.message_processor.add_new_message(
                RuntimeMessage(f"警告: 输出了错误的token: {regex_result!r}")
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class EndThinkPlugin(Plugin):
    """检查输出中是否有只有'</think>'的行并打断agent。"""

    async def after_token_generation(
        self, agent: "Agent", _answer: Answer, current_content: str
    ):
        """检查是否有一行只有'</think>'。"""
        lines = current_content.split("\n")
        for line in lines:
            if line.strip() == "</think>":
                await agent.interrupt(
                    "错误：检测到只有'</think>'的行，你将两条消息合并成了一条发送！请依次发送每条消息！",
                    "Agent消息合并错误，已纠正",
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


class OnlyReasoningPlugin(Plugin):
    """针对deepseek v3.2检测是否只思考不输出"""

    async def after_message_generation(
        self,
        answer: Answer,
        full_response: str,
        _tool_calls: List[Dict[str, JsonValue]],
    ):
        agent = self.group_chat.get_members("agent", Agent)
        model = agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility != "deepseek":
            return

        reasoning_content = answer.get_reasoning_message()

        if reasoning_content and not full_response.strip():
            agent.message_processor.update_appending_message(
                RuntimeMessage(
                    "检测到在思考后没有输出任何内容而是在</thinking>标签前就输出了工具调用等，应该在</thinking>标签后输出实际内容"
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
    """提供agent最近思考内容的插件。"""

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
            previous_reasoning_msg = SpoofedReasoningMessage(msgs[-6:])
            agent.message_processor.update_appending_message(
                previous_reasoning_msg, source="previous_reasoning", sort_value=1000
            )
        else:
            agent.message_processor.update_appending_message(
                None, source="previous_reasoning", sort_value=1000
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


class KimiK25ToolCallPlugin(Plugin):
    """处理kimi k2.5特殊工具调用格式的插件。"""

    async def after_message_generation(
        self,
        _answer: Answer,
        full_response: str,
        tool_calls: list[dict],
    ):
        if not full_response:
            return

        has_kimi_marker = "<|tool_calls_section_begin|><|tool_call_begin|>" in full_response
        has_correct_format = "```json toolcall" in full_response
        
        if has_kimi_marker and not has_correct_format:
            agent = self.group_chat.get_members("agent", Agent)
            if agent:
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        "警告：检测到kimi k2.5的特殊工具调用格式`<|tool_calls_section_begin|><|tool_call_begin|>`，"
                        "但没有正确的`json toolcall`代码块格式。\n"
                        "正确的工具调用格式是使用`json toolcall`代码块，例如：\n"
                        '```json toolcall\n'
                        '{"name": "tool_name", "arguments": {...}}\n'
                        '```'
                    )
                )
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING",
                        content="检测到kimi k2.5特殊工具调用格式，已提醒模型"
                    ),
                )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        lifecycle.register_after_message_generation(self.after_message_generation)


class RuntimeImitationPlugin(Plugin):
    """阻断deepseek模型模仿runtime输出的插件。"""

    async def after_token_generation(
        self,
        agent: "Agent",
        answer: Answer,
        current_content: str,
    ):
        """检查deepseek是否在模仿runtime输出并阻断。"""
        model = agent.get_current_model()

        if not isinstance(model, OpenAi) or model.compatibility != "deepseek":
            return False

        if matches := re.search(r"^\s*<<([a-z_]+)>>", current_content, re.MULTILINE):
            if matches.group(1) == "agent":
                await agent.interrupt(
                    "不要输出<<agent>>这个tag!", "Agent输出了无效标签，已纠正"
                )
            else:
                await agent.interrupt(
                    f"不要模仿{matches.group(1)}的输出！",
                    "Agent尝试模仿其他输出格式，已纠正",
                )
            return True

        if current_content.lstrip().startswith("<tool>{"):
            await agent.interrupt(
                "工具调用的格式是```json toolcall不是XML!",
                "Agent使用了错误的工具调用格式，已纠正",
            )
            return True

        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)
