"""工具调用管理插件。"""

import re

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.registry import Registry
from linhai.markdown_parser import extract_tool_calls
from linhai.base import Answer
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


class PromptFastAgentPlugin(Plugin):
    """限制特定LLM调用工具数量的插件"""

    def __init__(self, registry: Registry, max_toolcall_for_llm: dict[str, int]):
        super().__init__(registry)
        self.max_toolcall_for_llm = max_toolcall_for_llm
        self.speeding_counter = 0

    def _get_max_toolcall_for_current_model(self, agent: "Agent") -> int | None:
        """获取当前模型的最大工具调用数量，如果没有配置则返回None。"""
        model = agent.get_current_model()
        model_name = model.get_name()
        if model_name in self.max_toolcall_for_llm:
            return self.max_toolcall_for_llm[model_name]
        return None

    async def before_message_generation(self):
        """在消息生成前更新通知，显示当前模型的工具限制。"""
        agent = self.registry.get_member_typechecked("agent", Agent)

        if not agent.get_current_model().get_custom_toolcall_format():
            agent.message_processor.update_notification_message(
                None, source="prompt_fast_agent", sort_value=100
            )
            return

        max_toolcall = self._get_max_toolcall_for_current_model(agent)

        if max_toolcall is None:
            # 当前模型没有工具限制，清理notification消息
            agent.message_processor.update_notification_message(
                None, source="prompt_fast_agent", sort_value=100
            )
            return

        model = agent.get_current_model()
        model_name = model.get_name()
        # 更新notification消息，显示当前模型的工具限制
        agent.message_processor.update_notification_message(
            RuntimeMessage(
                t(
                    {
                        "zh_CN": f"你现在是{model_name}，为了避免一次性造成大量错误，runtime会在你调用超过{max_toolcall}个工具时打断你",
                        "en": f"You are now {model_name}, runtime will interrupt after {max_toolcall} tool calls to prevent mass errors",
                    }
                )
            ),
            source="prompt_fast_agent",
            sort_value=100,
        )

    async def after_token_generation(
        self,
        agent: "Agent",
        answer: Answer,
        current_content: str,
    ):
        max_toolcall = self._get_max_toolcall_for_current_model(agent)
        if max_toolcall is None:
            return False

        if not agent.get_current_model().get_custom_toolcall_format():
            return False

        if current_content.count("\n```json toolcall") > max_toolcall:
            model = agent.get_current_model()
            model_name = model.get_name()
            extra_message = ""
            if self.speeding_counter:
                extra_message = (
                    "从刚刚开始就一直在调用大量工具，你疯了？？？？"
                    + "？！？！" * self.speeding_counter
                )
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"禁止超速：你现在是{model_name}，为了避免一次性造成大量错误，runtime会在你调用超过{max_toolcall}个工具时打断你"
                    + extra_message
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content=f"针对性优化: 阻止{model_name}调用巨量工具",
                ),
            )
            answer.truncate()
            self.speeding_counter += 1
            return False
        self.speeding_counter = 0
        return False

    def register(self, lifecycle: "Lifecycle"):
        """注册before_message_generation和after_token_generation回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)
        lifecycle.after_token_generation.register(self.after_token_generation)


class SlowStartPlugin(Plugin):
    """防止agent在一开始就调用大量工具的插件"""

    def __init__(self, registry):
        super().__init__(registry)
        self.enabled = True

    async def after_token_generation(
        self, agent: "Agent", answer: Answer, current_content: str
    ) -> bool:
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        if not agent.get_current_model().get_custom_toolcall_format():
            return False

        if not self.enabled:
            return False

        if current_content.count("\n```json toolcall") > 8:
            self.enabled = False
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(level="WARNING", content="过量工具调用，已打断"),
            )
            answer.truncate()
            return False

        return False

    async def after_message_generation(
        self, parsed_answer, _full_response: str, tool_calls: list[dict]
    ):
        if not self.enabled:
            return
        if len(tool_calls) < 8:
            self.enabled = False

    def register(self, lifecycle: "Lifecycle"):
        """注册after_token_generation和after_message_generation回调。"""
        lifecycle.after_token_generation.register(self.after_token_generation)
        lifecycle.after_message_generation.register(self.after_message_generation)


class WeirdTokenPlugin(Plugin):
    """错误标记检查Plugin。"""

    async def after_token_generation(
        self,
        agent: "Agent",
        answer: Answer,
        current_content: str,
    ):
        """检查`<｜end▁of▁[a-z]+｜>`和minimax的<tool_call>"""
        pattern = r"<｜end▁of▁[a-z]+｜>"
        model = agent.get_current_model()

        for line in current_content.split("\n"):
            if re.search(pattern, line):
                await agent.message_processor.add_new_message(
                    RuntimeMessage(
                        "检测到错误结束标记：在一行中有`<｜end▁of▁[a-z]+｜>`且前面都是文字，已截断输出"
                    )
                )
                answer.truncate()
                return False
            if (
                model.get_compatibility() == "minimax"
                and model.get_custom_toolcall_format()
                and line == "<tool_call>"
            ):
                await agent.agent_llm.interrupt(
                    "检测到错误工具调用标记：输出了错误的工具调用: <tool_call>\n你应该使用json toolcall代码块调用工具！",
                    "检测到错误工具调用格式",
                )
                return True
        return False

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.after_token_generation.register(self.after_token_generation)


class SingleToolCallReminderPlugin(Plugin):
    """提醒agent不要连续多次只调用单个工具的插件。"""

    def __init__(self, registry):
        super().__init__(registry)
        self.single_tool_call_count = 0

    async def after_message_generation(
        self, parsed_answer, _full_response: str, tool_calls: list[dict]
    ):
        """检查是否连续多次只调用了一个工具。"""
        agent = self.registry.get_member_typechecked("agent", Agent)

        if not agent.get_current_model().get_custom_toolcall_format():
            agent.message_processor.update_notification_message(
                None, source="single_tool_call_reminder", sort_value=0
            )
            return

        if len(tool_calls) == 1:
            self.single_tool_call_count += 1

            if self.single_tool_call_count >= 2:
                agent.message_processor.update_notification_message(
                    RuntimeMessage(
                        t(
                            {
                                "zh_CN": (
                                    f"注意：你连续{self.single_tool_call_count}次仅调用一个工具，"
                                    "除开特殊原因不要每次只调用一个工具！"
                                    "\n多个工具调用的语法为markdown语法，在一个回答中输出多个json toolcall代码块，如:\n\n"
                                    '```json toolcall\n{"name": "read_file", ...}\n```\n\n'
                                    '```json toolcall\n{"name": "read_file", ...}\n```\n'
                                ),
                                "en": (
                                    f"Note: You have called only one tool for {self.single_tool_call_count} consecutive times. "
                                    "Avoid calling only one tool at a time unless there's a special reason!"
                                    "\nMultiple tool calls use markdown syntax, output multiple json toolcall code blocks in one response, e.g.:\n\n"
                                    '```json toolcall\n{"name": "read_file", ...}\n```\n\n'
                                    '```json toolcall\n{"name": "read_file", ...}\n```'
                                ),
                            }
                        )
                    ),
                    source="single_tool_call_reminder",
                    sort_value=0,
                )
            else:
                agent.message_processor.update_notification_message(
                    None, source="single_tool_call_reminder", sort_value=0
                )
        else:
            self.single_tool_call_count = 0
            agent.message_processor.update_notification_message(
                None, source="single_tool_call_reminder", sort_value=0
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class ToolCallInReasoningPlugin(Plugin):
    """检测思考内容中工具调用的插件。"""

    async def after_message_generation(
        self,
        parsed_answer,
        _full_response: str,
        tool_calls: List[Dict[str, JsonValue]],
    ):
        """检查推理内容中是否包含工具调用，且实际输出中没有调用工具。"""
        agent = self.registry.get_member_typechecked("agent", Agent)

        if not agent.get_current_model().get_custom_toolcall_format():
            return

        reasoning_content = parsed_answer._answer.get_reasoning_message()
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

        missing_tools = reasoning_tool_names - actual_tool_names
        if not missing_tools:
            return

        missing_tool_names = list(missing_tools)

        if len(missing_tool_names) == 1:
            agent_warning_message = f"警告：你在推理内容中调用了工具'{missing_tool_names[0]}'，但推理内容中的工具调用不会实际执行！"
            ui_warning_message = f"推理内容中检测到工具调用: {missing_tool_names[0]}"
        else:
            agent_warning_message = f"警告：你在推理内容中调用了工具{missing_tool_names}，但推理内容中的工具调用不会实际执行！"
            ui_warning_message = (
                f"推理内容中检测到工具调用: {', '.join(missing_tool_names)}"
            )

        await agent.message_processor.add_new_message(
            RuntimeMessage(agent_warning_message)
        )
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="WARNING", content=ui_warning_message),
        )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)


class LoadImageUrlWarningPlugin(Plugin):
    """检查load_image工具的参数是否为URL的插件。"""

    async def after_message_generation(
        self,
        parsed_answer,
        _full_response: str,
        tool_calls: List[Dict[str, JsonValue]],
    ):
        """检查工具调用中load_image的参数是否为URL。"""
        agent = self.registry.get_member_typechecked("agent", Agent)
        load_image_toolcalls = [
            tool_call
            for tool_call in tool_calls
            if tool_call.get("name") == "load_image" and "arguments" in tool_call
        ]
        file_paths = [
            str(tool_call["arguments"].get("image_filepath"))
            for tool_call in load_image_toolcalls
            if isinstance(tool_call["arguments"], dict)
        ]
        if any(
            file_path.startswith(protocol)
            for protocol in ("http://", "https://", "ftp://")
            for file_path in file_paths
        ):
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "警告：load_image工具的参数image_filepath看起来是一个URL，但load_image只支持本地文件路径！请先下载图片到master_host"
                )
            )
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="WARNING",
                    content="load_image工具的参数为URL，已警告agent",
                ),
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.after_message_generation.register(self.after_message_generation)
