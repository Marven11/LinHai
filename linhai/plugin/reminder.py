from pathlib import Path

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import FileContentMessage, RuntimeMessage
from linhai.plugin.message_checkers import Plugin
from linhai.group_chat import GroupChat


class ReminderPlugin(Plugin):
    """REMINDER插件：在每次消息生成前更新notification messages。"""

    def __init__(self, group_chat: GroupChat, claw_dir: Path):
        super().__init__(group_chat)
        self.claw_dir = claw_dir
        self.reminder_file = claw_dir / "REMINDER.md"
        self.soul_file = claw_dir / "SOUL.md"

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ) -> None:
        """在每次消息生成前读取REMINDER.md和SOUL.md并更新notification messages。"""
        if not self.group_chat.has_member("agent"):
            return

        agent = self.group_chat.get_member_typechecked("agent", Agent)

        if self.reminder_file.exists():
            content = self.reminder_file.read_text(encoding="utf-8").strip()
            agent.message_processor.update_notification_message(
                RuntimeMessage(content), source="reminder", sort_value=1000
            )

        if self.soul_file.exists():
            content = self.soul_file.read_text(encoding="utf-8").strip()
            agent.message_processor.update_notification_message(
                FileContentMessage(
                    filepath=str(self.soul_file),
                    content=content,
                    show_line_numbers=False,
                ),
                source="soul",
                sort_value=2000,
            )

    def register(self, lifecycle: Lifecycle):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
