from pathlib import Path
from typing import TYPE_CHECKING

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.agent.planning import PlanningPromptMessage
from linhai.group_chat import GroupChat
from linhai.llm import Answer, UserMessage
from linhai.utils import CliRuntimeNotice
from linhai.plugin.file_operations import Plugin

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class PlanningStatusReminderPlugin(Plugin):
    """提醒修改STATUS.md和TODOLIST.md的插件。"""

    def __init__(self, group_chat: GroupChat):
        super().__init__(group_chat)
        self.group_chat = group_chat
        self.status_counter = 0
        self.todolist_counter = 0
        self.planning_folder: Path | None = None

    def _get_planning_folder(self) -> Path | None:
        if self.planning_folder is not None:
            return self.planning_folder

        agent = self.group_chat.get_member_typechecked("agent", Agent)
        if agent is None:
            return None

        for msg in agent.message_processor.get_messages():
            if isinstance(msg, PlanningPromptMessage):
                self.planning_folder = msg.planning_folder
                return self.planning_folder

        return None

    def _get_current_state(self) -> str:
        from linhai.agent.orchestration import AgentContextOrchestration

        agent = self.group_chat.get_member_typechecked("agent", Agent)
        orchestration = self.group_chat.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )

        if agent is None or orchestration is None:
            return "绿灯"

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return "绿灯"

        context = orchestration.compute_orchestration_context("", threshold_info)
        return context["current_state"]

    def _check_modifications(
        self, tool_calls: list[dict], planning_folder: Path
    ) -> tuple[bool, bool]:
        write_tools = {"write_file", "replace_file_content", "modify_file_with_sed"}
        status_file = planning_folder / "STATUS.md"
        todolist_file = planning_folder / "TODOLIST.md"

        status_modified = False
        todolist_modified = False

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_arguments = tool_call.get("arguments", {})

            if tool_name not in write_tools:
                continue

            filepath = tool_arguments.get("filepath")
            if not filepath:
                continue

            if Path(filepath).absolute() == status_file:
                status_modified = True
            elif Path(filepath).absolute() == todolist_file:
                todolist_modified = True

        return status_modified, todolist_modified

    def _update_counters(
        self, status_modified: bool, todolist_modified: bool, current_state: str
    ) -> None:
        if current_state == "红灯":
            return
        self.status_counter = 0 if status_modified else (self.status_counter + 1)
        self.todolist_counter = 0 if todolist_modified else (self.todolist_counter + 1)

    async def _update_notifications(self, current_state: str) -> None:
        if current_state == "红灯":
            agent = self.group_chat.get_member_typechecked("agent", Agent)
            if agent:
                agent.message_processor.update_notification_message(
                    None, source="planning_status_reminder", sort_value=0
                )
                agent.message_processor.update_notification_message(
                    None, source="planning_todolist_reminder", sort_value=0
                )
            return

        agent = self.group_chat.get_member_typechecked("agent", Agent)
        if agent is None:
            return

        if self.status_counter >= 3:
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    f"你已经连续{self.status_counter}次没有修改STATUS.md，你偏离计划了吗？"
                ),
                source="planning_status_reminder",
                sort_value=0,
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content=f"警告agent：连续{self.status_counter}次未修改STATUS.md",
                ),
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="planning_status_reminder", sort_value=0
            )

        if self.todolist_counter >= 8:
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    f"你已经连续{self.todolist_counter}次没有修改TODOLIST.md，你偏离任务了吗？你应该如何修改TODOLIST.md?当前任务是否需要分解？当前任务是否需要被推迟？"
                ),
                source="planning_todolist_reminder",
                sort_value=0,
            )
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content=f"警告agent：连续{self.todolist_counter}次未修改TODOLIST.md",
                ),
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="planning_todolist_reminder", sort_value=0
            )

    async def after_message_generation(
        self,
        answer: Answer,
        full_response: str,
        tool_calls: list[dict],
    ) -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        if not tool_calls:
            return

        current_state = self._get_current_state()
        status_modified, todolist_modified = self._check_modifications(
            tool_calls, planning_folder
        )

        self._update_counters(status_modified, todolist_modified, current_state)

        await self._update_notifications(current_state)

    def register(self, lifecycle: Lifecycle):
        lifecycle.register_after_message_generation(self.after_message_generation)


class UserInputRuntimeMessagePlugin(Plugin):
    """在用户输入消息后添加RuntimeMessage的插件。"""

    def __init__(self, group_chat: GroupChat):
        super().__init__(group_chat)
        self.group_chat = group_chat

    async def after_message_generation(
        self,
        answer: Answer,
        full_response: str,
        tool_calls: list[dict],
    ) -> None:
        agent = self.group_chat.get_member_typechecked("agent", Agent)
        if agent is None:
            return

        messages = agent.message_processor.get_messages()
        if not messages:
            return

        last_msg = messages[-1]
        if not isinstance(last_msg, UserMessage):
            return

        agent.message_processor.add_new_message(
            RuntimeMessage(
                "用户提出的问题？指示？重新规划？重新设计？规划检查？优先规划？记录用户原文？"
            )
        )

    def register(self, lifecycle: Lifecycle):
        lifecycle.register_after_message_generation(self.after_message_generation)
