from pathlib import Path
from typing import TYPE_CHECKING

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage
from linhai.plugin.message_checkers import Plugin
from linhai.group_chat import GroupChat


class ReminderPlugin(Plugin):
    """REMINDER插件：在每次消息生成前更新notification messages。"""

    def __init__(self, group_chat: GroupChat, claw_dir: Path):
        super().__init__(group_chat)
        self.claw_dir = claw_dir
        self.reminder_file = claw_dir / "REMINDER.md"

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ) -> None:
        """在每次消息生成前读取REMINDER.md并更新notification messages。"""
        if not self.reminder_file.exists():
            return

        if not self.group_chat.has_member("agent"):
            return

        content = self.reminder_file.read_text(encoding="utf-8").strip()
        agent = self.group_chat.get_member_typechecked("agent", Agent)
        agent.message_processor.update_notification_message(
            RuntimeMessage(content), source="reminder", sort_value=1000
        )

    def register(self, lifecycle: Lifecycle):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
