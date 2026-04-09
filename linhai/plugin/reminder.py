from pathlib import Path
from typing import Union

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.plugin.message_checkers import Plugin
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


class ReminderPlugin(Plugin):
    """REMINDER插件：在每次消息生成前更新notification messages。"""

    def __init__(self, registry: Registry, claw_dir: Path):
        super().__init__(registry)
        self.claw_dir = claw_dir
        self.reminder_file = claw_dir / "REMINDER.md"
        self.soul_file = claw_dir / "SOUL.md"

    async def before_message_generation(self) -> None:
        """在每次消息生成前读取REMINDER.md和SOUL.md并更新notification messages。"""
        if not self.registry.has_member("agent"):
            return

        agent = self.registry.get_member_typechecked("agent", Agent)

        if self.reminder_file.exists():
            content = self.reminder_file.read_text(encoding="utf-8").strip()
            agent.message_processor.update_notification_message(
                RuntimeMessage(content), source="reminder", sort_value=1000
            )

    def register(self, lifecycle: Lifecycle):
        """注册到before_message_generation回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)


class ReminderWriteGuardPlugin(Plugin):
    """拦截对REMINDER.md的过长写入。"""

    MAX_LENGTH = 100

    def __init__(self, registry: Registry, claw_dir: Path):
        super().__init__(registry)
        self.reminder_file = (claw_dir / "REMINDER.md").resolve()

    def _is_reminder_file(self, filepath: str) -> bool:
        if not filepath:
            return False
        return Path(filepath).resolve() == self.reminder_file

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        _with_secret: list[str] | None,
    ) -> Union[ToolResultSuccess, ToolResultFailed, dict, None]:
        if tool_name == "write_file":
            return self._check_write_file(toolcall_arguments)
        if tool_name == "replace_file_content":
            return self._check_replace_file_content(toolcall_arguments)
        return None

    def _check_write_file(self, arguments: dict) -> ToolResultFailed | None:
        filepath = arguments.get("filepath")
        if not filepath or not self._is_reminder_file(filepath):
            return None

        content = arguments.get("content", "")
        stripped = content.strip()
        if "\n" in stripped or len(stripped) > self.MAX_LENGTH:
            return ToolResultFailed(
                content=(
                    f"REMINDER.md写入被拦截：内容过长（{len(stripped)}字符）或包含换行符。"
                    f"REMINDER.md应保持简短（不超过{self.MAX_LENGTH}字符，单行）。"
                )
            )
        return None

    def _simulate_replace(self, arguments: dict) -> str | None:
        if not self.reminder_file.exists():
            return None

        old = arguments.get("old", "")
        new = arguments.get("new", "")
        replace_times = arguments.get("replace_times")

        current = self.reminder_file.read_text(encoding="utf-8")

        if replace_times is None:
            if current.count(old) != 1:
                return None
            return current.replace(old, new, 1)
        if replace_times == -1:
            return current.replace(old, new)
        if isinstance(replace_times, int) and replace_times > 0:
            return current.replace(old, new, replace_times)
        return None

    def _check_replace_file_content(self, arguments: dict) -> ToolResultFailed | None:
        filepath = arguments.get("filepath")
        if not filepath or not self._is_reminder_file(filepath):
            return None

        new_content = arguments.get("new", "")
        if "\n" in new_content:
            return ToolResultFailed(
                content=(
                    "REMINDER.md写入被拦截：替换内容包含换行符。"
                    f"REMINDER.md应保持简短（不超过{self.MAX_LENGTH}字符，单行）。"
                )
            )

        replaced = self._simulate_replace(arguments)
        if replaced is not None and len(replaced) > self.MAX_LENGTH:
            return ToolResultFailed(
                content=(
                    f"REMINDER.md写入被拦截：替换后文件过长（{len(replaced)}字符）。"
                    f"REMINDER.md应保持简短（不超过{self.MAX_LENGTH}字符，单行）。"
                )
            )
        return None

    def register(self, lifecycle: Lifecycle):
        lifecycle.before_tool_call.register(self.before_tool_call)
