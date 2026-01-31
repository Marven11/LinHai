"""任务规划插件模块，用于让Agent在调用工具前提前规划任务。"""

from __future__ import annotations

from typing import Dict, List, Union, TypedDict

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.plugin import Plugin
import linhai.agent as linhai_agent
from ..llm import Answer
from ..utils import CliRuntimeNotice
from linhai.llm import SystemMessage
from linhai.agent.base import RuntimeMessage


class ToolCall(TypedDict):
    """工具调用参数的具体类型定义。"""

    name: str
    arguments: Dict[str, Union[str, int, float, bool, None]]


class TaskPlanningPromptPlugin(Plugin):
    """任务规划提示插件。

    当用户在配置中打开了规划任务功能（enable_task_planning = true）时，
    此插件会向Agent添加提示消息，要求Agent在每个工具调用前输出任务规划。
    任务规划格式为嵌套无序列表，使用`[ ]`和`[x]`标记完成状态。
    """

    async def before_agent_loop(self, agent: Agent) -> None:
        """在Agent循环开始前添加任务规划提示。

        这是插件系统的标准设计模式：通过副作用修改SystemMessage状态。
        返回None符合插件接口规范，允许其他插件继续处理。
        """

        system_message = self.group_chat.get_members("system_message", SystemMessage)
        system_message.add_rule(
            "TASK PLANNING",
            "你需要在调用工具前提前规划任务。任务规划格式要求：\n"
            "- 在```json toolcall前的一段嵌套无序列表，使用`[ ]`和`[x]`标记完成的和未完成的任务\n"
            "- 例子：\n"
            "  - [ ] 探索代码\n"
            "    - [x] 列出当前文件夹\n"
            "    - [x] 搜索xxx\n"
            "    - [ ] 根据当前文件夹的内容继续探索其中的内容\n"
            "  - [ ] 开始编写代码\n"
            "    - [ ] 完成xxx\n"
            "    - [ ] 完成unittest\n"
            "如果你连续3次没有输出任务规划就调用工具，将会被打断。",
        )
        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="INFO", content="SystemMessage已添加任务规划规则"),
        )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content="任务规划提示已添加：Agent需要在调用工具前输出任务规划",
            ),
        )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到before_agent_loop回调。"""
        lifecycle.register_before_agent_loop(self.before_agent_loop)


class TaskPlanningEnforcementPlugin(Plugin):
    """任务规划强制执行插件，检测Agent是否输出任务规划。"""

    def __init__(self, group_chat: GroupChat):
        super().__init__(group_chat)
        self.no_planning_counter = 0

    async def after_message_generation(
        self,
        _answer: Answer,
        full_response: str,
        tool_calls: list[dict],
    ) -> None:
        """检查Agent是否输出了任务规划。"""

        has_planning = False
        lines = full_response.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                has_planning = True
                break

        if has_planning:

            self.no_planning_counter = 0
            self.group_chat.get_members(
                "agent", Agent
            ).message_processor.update_appending_message(
                None, source="task_planning_reminder", sort_value=0
            )
        elif tool_calls:

            self.no_planning_counter += 1

            if self.no_planning_counter == 1:

                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="INFO", content="Agent没有输出任务规划，已提醒"
                    ),
                )
                self.group_chat.get_members(
                    "agent", Agent
                ).message_processor.update_appending_message(
                    RuntimeMessage(
                        "注意：你没有输出任务规划！如果连续3次不输出任务规划，将会被打断回答。"
                    ),
                    source="task_planning_reminder",
                    sort_value=0,
                )
            elif self.no_planning_counter == 2:

                self.group_chat.get_members(
                    "agent", Agent
                ).message_processor.update_appending_message(
                    RuntimeMessage(
                        "警告：你已经连续2次没有输出任务规划！如果下一次仍然不输出任务规划，将会被打断回答！"
                    ),
                    source="task_planning_reminder",
                    sort_value=0,
                )
            elif self.no_planning_counter >= 3:

                await self.group_chat.get_members("agent", Agent).interrupt(
                    "错误：你已经连续3次没有输出任务规划！你必须先在调用工具前输出任务规划！",
                    "Agent连续3次未输出任务规划，已打断",
                )
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content="Agent连续3次未输出任务规划，已打断"
                    ),
                )
                # 重置计数器
                self.no_planning_counter = 0

    async def after_token_generation(
        self, agent: "Agent", _answer: Answer, current_content: str
    ) -> bool:
        """检查是否应该打断Agent。"""

        if "```json toolcall" in current_content:
            # 检查当前内容中是否有任务规划
            lines = current_content.split("\n")
            has_planning = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                    has_planning = True
                    break

            if not has_planning and self.no_planning_counter >= 3:
                # 连续3次没有输出任务规划，需要打断token生成
                return True

        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
        lifecycle.register_after_token_generation(self.after_token_generation)
