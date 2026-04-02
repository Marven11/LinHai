from pathlib import Path

from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import FileContentMessage, RuntimeMessage
from linhai.plugin.message_checkers import Plugin
from linhai.registry import Registry


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
        lifecycle.register_before_message_generation(self.before_message_generation)
