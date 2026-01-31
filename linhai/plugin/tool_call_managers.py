"""工具调用管理插件。"""

import re

from abc import ABC, abstractmethod
from typing import Dict, List

from linhai.agent import Agent
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.markdown_parser import extract_tool_calls
from linhai.llm import Answer, OpenAi
from linhai.utils import CliRuntimeNotice

from .helpers import JsonValue


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class PromptFastAgentPlugin(Plugin):
    """禁止minimax m2/glm 4.6疯狂调用工具的插件"""

    MAX_TOOLCALL_COUNT = 5

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.speeding_counter = 0

    async def before_agent_loop(self, agent: "Agent"):
        """在Agent循环开始前添加特定模型提示。"""
        model = agent.get_current_model()

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
        return

    async def after_token_generation(
        self,
        agent: "Agent",
        answer: Answer,
        current_content: str,
    ):
        model = agent.get_current_model()
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
        self, agent: "Agent", answer: Answer, current_content: str
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
                    "检测到错误工具调用标记：输出了错误的工具调用: <tool_call>\n你应该使用json toolcall代码块调用工具！",
                    "检测到错误工具调用格式",
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_token_generation回调。"""
        lifecycle.register_after_token_generation(self.after_token_generation)


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


class ToolCallInReasoningPlugin(Plugin):
    """检测思考内容中工具调用的插件。"""

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

        agent.message_processor.add_new_message(RuntimeMessage(agent_warning_message))
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="WARNING", content=ui_warning_message),
        )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
