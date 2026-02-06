from pathlib import Path
from typing import Literal, TYPE_CHECKING, Union

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.agent.planning import PlanningPromptMessage
from linhai.group_chat import GroupChat
from linhai.llm import Answer, Message, UserMessage
from linhai.utils import CliRuntimeNotice
from linhai.plugin.file_operations import Plugin

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class PlanningStatusReminderPlugin(Plugin):
    """提醒修改STATUS.md和TODOLIST.md的插件。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.status_counter = 0
        self.todolist_counter = 0
        self.planning_folder: Path | None = None

    def _get_planning_folder(self) -> Path | None:
        if self.planning_folder is not None:
            return self.planning_folder

        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            return None

        for msg in agent.message_processor.get_messages():
            if isinstance(msg, PlanningPromptMessage):
                self.planning_folder = msg.planning_folder
                return self.planning_folder

        return None

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
        if status != "success":
            return None

        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return None

        self._update_counters(tool_name, toolcall_arguments, planning_folder)
        self._clear_notifications_if_needed(tool_name, toolcall_arguments, planning_folder)
        await self._send_warnings_if_needed()

        return None

    def _update_counters(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        planning_folder: Path
    ) -> None:
        write_tools = {"write_file", "replace_file_content", "modify_file_with_sed"}
        
        if tool_name not in write_tools:
            self.status_counter += 1
            self.todolist_counter += 1
            return

        filepath = toolcall_arguments.get("filepath")
        if not filepath:
            self.status_counter += 1
            self.todolist_counter += 1
            return
        
        status_file = planning_folder / "STATUS.md"
        todolist_file = planning_folder / "TODOLIST.md"
        
        if Path(filepath) == status_file:
            self.status_counter = 0
        elif Path(filepath) == todolist_file:
            self.todolist_counter = 0
        else:
            self.status_counter += 1
            self.todolist_counter += 1

    def _clear_notifications_if_needed(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        planning_folder: Path
    ) -> None:
        if tool_name not in {"write_file", "replace_file_content", "modify_file_with_sed"}:
            return

        filepath = toolcall_arguments.get("filepath")
        if not filepath:
            return

        agent = self.group_chat.get_members("agent", Agent)
        if not agent:
            return

        status_file = planning_folder / "STATUS.md"
        todolist_file = planning_folder / "TODOLIST.md"
        
        if Path(filepath) == status_file:
            agent.message_processor.update_notification_message(
                None, source="planning_status_reminder", sort_value=0
            )
        elif Path(filepath) == todolist_file:
            agent.message_processor.update_notification_message(
                None, source="planning_todolist_reminder", sort_value=0
            )

    async def _send_warnings_if_needed(self) -> None:
        agent = self.group_chat.get_members("agent", Agent)
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

    def register(self, lifecycle: Lifecycle):
        lifecycle.register_on_tool_result(self.on_tool_result)


class UserInputRuntimeMessagePlugin(Plugin):
    """在用户输入消息后添加RuntimeMessage的插件。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def after_message_generation(
        self,
        _answer: Answer,
        _full_response: str,
        _tool_calls: list[dict],
    ):
        agent = self.group_chat.get_members("agent", Agent)
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
