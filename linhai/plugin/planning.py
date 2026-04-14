from pathlib import Path
from typing import TYPE_CHECKING, Optional
import re
from os import access, R_OK

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage, FileContentMessage
from linhai.agent.state_machine import AgentStateMachine
from linhai.agent.planning import PlanningPromptMessage
from linhai.registry import Registry
from linhai.base import Answer, UserMessage, Message
from linhai.plugin.file_operations import Plugin

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class PlanningStatusReminderPlugin(Plugin):
    """提醒修改STATUS.md和TODOLIST.md的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry
        self.status_counter = 0
        self.todolist_counter = 0
        self.planning_folder: Optional[Path] = None

    def _get_planning_folder(self) -> Optional[Path]:
        if self.planning_folder is not None:
            return self.planning_folder

        conversation_folder = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        if conversation_folder is None:
            return None

        self.planning_folder = conversation_folder / "planning"
        return self.planning_folder

    def _get_current_state(self) -> str:
        from linhai.agent.orchestration import AgentContextOrchestration

        agent = self.registry.get_member_typechecked("agent", Agent)
        orchestration = self.registry.get_member_typechecked(
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
        write_tools = {"write_file", "replace_file_content"}
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
            agent = self.registry.get_member_typechecked("agent", Agent)
            if agent:
                agent.message_processor.update_notification_message(
                    None, source="planning_status_reminder", sort_value=0
                )
                agent.message_processor.update_notification_message(
                    None, source="planning_todolist_reminder", sort_value=0
                )
            return

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            return

        if self.status_counter >= 5:
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    f"你已经连续{self.status_counter}次没有修改STATUS.md，你偏离计划了吗？"
                ),
                source="planning_status_reminder",
                sort_value=0,
            )
        elif self.status_counter >= 3:
            agent.message_processor.update_notification_message(
                RuntimeMessage("提醒：你应该更新STATUS.md以反应当前状态"),
                source="planning_status_reminder",
                sort_value=0,
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="planning_status_reminder", sort_value=0
            )

        if self.todolist_counter >= 8:
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    f"你已经连续{self.todolist_counter}次没有修改TODOLIST.md，你偏离任务了吗？你应该如何修改TODOLIST.md? 当前任务是否需要分解？当前任务是否需要被推迟？"
                ),
                source="planning_todolist_reminder",
                sort_value=0,
            )
        if self.todolist_counter >= 6:
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    f"你已经连续{self.todolist_counter}次没有修改TODOLIST.md，你应该如何修改TODOLIST.md? 当前任务是否需要分解？当前任务是否需要被推迟？"
                ),
                source="planning_todolist_reminder",
                sort_value=0,
            )
        else:
            agent.message_processor.update_notification_message(
                None, source="planning_todolist_reminder", sort_value=0
            )

    async def after_message_generation(
        self,
        parsed_answer,
        _full_response: str,
        tool_calls: list[dict],
    ) -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        current_state = self._get_current_state()

        if tool_calls:
            status_modified, todolist_modified = self._check_modifications(
                tool_calls, planning_folder
            )
            self._update_counters(status_modified, todolist_modified, current_state)

        await self._update_notifications(current_state)

    def register(self, lifecycle: Lifecycle):
        lifecycle.after_message_generation.register(self.after_message_generation)


class TodolistCheckerPlugin(Plugin):
    """检查TODOLIST.md是否有未完成任务，防止提前暂停的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry

    def _get_planning_folder(self) -> Optional[Path]:
        conversation_folder = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        if conversation_folder is None:
            return None

        return conversation_folder / "planning"

    def _has_unfinished_tasks(self, todolist_path: Path) -> bool:
        if not todolist_path.exists():
            return False
        if not access(todolist_path, R_OK):
            return False
        content = todolist_path.read_text(encoding="utf-8")
        pattern = r"^\s*-\s+\[(\s|\.)\]"
        matches = re.findall(pattern, content, flags=re.MULTILINE)
        return any(status in (" ", ".") for status in matches)

    async def before_waiting_user(self, agent: "linhai_agent") -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        todolist_path = planning_folder / "TODOLIST.md"
        if not todolist_path.exists():
            return

        if self._has_unfinished_tasks(todolist_path):
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "错误：当前TODOLIST.md仍有未完成项，你是不是搞错什么了？"
                    "你是不是完全忘记了你应该做什么？你是不是遗漏了用户的要求？"
                    "你是否搞错了用户的最终目标？你有考虑用户的验收标准是什么吗？"
                    "是否还有其他要求应该列为未完成项？当前的未完成项应该怎么完成？"
                    "你应该重新审视用户的**所有要求**，**诚实地**列出所有已经完成的和没有完成的任务！"
                    "完成的任务**必须**标记为已经完成！没有完成的任务**必须**标记为没有完成！！"
                )
            )
            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            state_machine.transition_to_working()

    def register(self, lifecycle: Lifecycle):
        lifecycle.before_waiting_user.register(self.before_waiting_user)


class DesignMdReminderPlugin(Plugin):
    """在消息清理后提醒重新读取DESIGN.md，重新读取后提醒调整计划的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry
        self._design_notification_active = False
        self._design_reminded = False
        self.planning_folder: Optional[Path] = None

    def _get_planning_folder(self) -> Optional[Path]:
        if self.planning_folder is not None:
            return self.planning_folder

        conversation_folder = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        if conversation_folder is None:
            return None

        self.planning_folder = conversation_folder / "planning"
        return self.planning_folder

    def _is_design_in_messages(self, messages: list[Message]) -> bool:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return True

        design_resolved = (planning_folder / "DESIGN.md").resolve()
        for msg in messages:
            if isinstance(msg, FileContentMessage):
                if Path(msg.filepath).resolve() == design_resolved:
                    return True
        return False

    async def after_cache_invalidate(
        self, agent: "linhai_agent", messages: list[Message]
    ) -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        all_messages = agent.message_processor.get_messages()
        if not self._is_design_in_messages(all_messages):
            self._design_notification_active = True
            self._design_reminded = False
            agent.message_processor.update_notification_message(
                RuntimeMessage(
                    "当前没有查看DESIGN.md的内容，你应该重新读取再继续任务吗？"
                    "你应该如何修改DESIGN.md以符合任务的最新要求？"
                ),
                source="planning_design_reminder",
                sort_value=0,
            )

    async def before_message_generation(self) -> None:
        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            return

        all_messages = agent.message_processor.get_messages()
        if (
            self._is_design_in_messages(all_messages)
            and self._design_notification_active
            and not self._design_reminded
        ):
            self._design_notification_active = False
            self._design_reminded = True
            agent.message_processor.update_notification_message(
                None, source="planning_design_reminder", sort_value=0
            )
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    "你重新查看了DESIGN.md的内容，你应该如何调整计划？"
                    "当前内容是否需要补充或者修改？"
                )
            )

    def register(self, lifecycle: Lifecycle):
        lifecycle.after_cache_invalidate.register(self.after_cache_invalidate)
        lifecycle.before_message_generation.register(self.before_message_generation)


class PlanningInitOverridePlugin(Plugin):
    """在agent循环开始前提醒使用override=true初始化规划文件的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry

    async def before_agent_loop(self, agent: "linhai_agent") -> None:
        await agent.message_processor.add_new_message(
            RuntimeMessage(
                "重要提醒：在初始化STATUS.md、TODOLIST.md、DESIGN.md等规划文件时，"
                "必须使用override=true参数覆盖已有文件，否则写入会因文件已存在而失败。"
            )
        )

    def register(self, lifecycle: Lifecycle):
        lifecycle.before_agent_loop.register(self.before_agent_loop)


class UserInputRuntimeMessagePlugin(Plugin):
    """在用户输入消息后添加RuntimeMessage的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry

    async def after_message_generation(
        self,
        parsed_answer,
        _full_response: str,
        _tool_calls: list[dict],
    ) -> None:
        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            return

        messages = agent.message_processor.get_messages()
        if not messages:
            return

        last_msg = messages[-1]
        if not isinstance(last_msg, UserMessage):
            return

        await agent.message_processor.add_new_message(
            RuntimeMessage(
                "用户提出的问题？指示？重新规划？重新设计？规划检查？优先规划？记录用户原文？"
            )
        )

    def register(self, lifecycle: Lifecycle):
        lifecycle.after_message_generation.register(self.after_message_generation)


class PlanningHeadingCheckPlugin(Plugin):
    """检查planning文件中是否包含一级标题的插件。"""

    def __init__(self, registry: Registry):
        super().__init__(registry)
        self.registry = registry
        self.planning_folder: Optional[Path] = None

    def _get_planning_folder(self) -> Optional[Path]:
        if self.planning_folder is not None:
            return self.planning_folder

        conversation_folder = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        if conversation_folder is None:
            return None

        self.planning_folder = conversation_folder / "planning"
        return self.planning_folder

    def _is_planning_file(self, filepath: str, planning_folder: Path) -> bool:
        """检查文件是否为planning文件夹下的STATUS.md、TODOLIST.md或DESIGN.md"""
        if not filepath or not isinstance(filepath, str):
            return False

        filepath_obj = Path(filepath)
        abs_path = filepath_obj.absolute()

        planning_files = [
            planning_folder / "STATUS.md",
            planning_folder / "TODOLIST.md",
            planning_folder / "DESIGN.md",
        ]

        for pf in planning_files:
            if abs_path == pf.absolute():
                return True
        return False

    def _contains_heading(self, content: str) -> bool:
        """检查内容是否包含一级标题（以# 开头的行）"""
        return any(line.startswith("# ") for line in content.split("\n"))

    async def after_message_generation(
        self,
        parsed_answer,
        _full_response: str,
        tool_calls: list[dict],
    ) -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        write_tools = {"write_file", "replace_file_content"}
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            if tool_name not in write_tools:
                continue

            tool_arguments = tool_call.get("arguments", {})
            filepath = tool_arguments.get("filepath")
            content = None
            if tool_name == "write_file":
                content = tool_arguments.get("content")
            elif tool_name == "replace_file_content":
                content = tool_arguments.get("new")

            if not filepath or content is None:
                continue

            if not self._is_planning_file(filepath, planning_folder):
                continue

            if self._contains_heading(content):
                agent = self.registry.get_member_typechecked("agent", Agent)
                if agent is None:
                    return

                filename = Path(filepath).name
                await agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"你刚刚向planning文件{filename}添加了内容`# xxx`，这是一级标题吗？这是违反system prompt的标题吗？你之后要如何改进文件内容以符合要求？"
                    )
                )

    def register(self, lifecycle: Lifecycle):
        lifecycle.after_message_generation.register(self.after_message_generation)
