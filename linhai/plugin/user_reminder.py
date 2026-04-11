from pathlib import Path

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.plugin.message_checkers import Plugin
from linhai.registry import Registry


class UserReminderPlugin(Plugin):
    """用户提醒插件：在每次消息生成前读取用户配置的提醒文件并更新notification messages。"""

    def __init__(self, registry: Registry, reminder_file_path: str):
        super().__init__(registry)
        self.reminder_file_path = reminder_file_path

    async def before_message_generation(self) -> None:
        """在每次消息生成前读取用户提醒文件并更新notification messages。"""
        reminder_file = Path(self.reminder_file_path).expanduser()
        if not reminder_file.is_absolute():
            config_path = self.registry.members.get("config_path")
            if isinstance(config_path, (str, Path)):
                config_dir = Path(config_path).parent
                reminder_file = config_dir / reminder_file

        if not reminder_file.exists():
            return

        content = reminder_file.read_text(encoding="utf-8").strip()
        if not content:
            return

        agent = self.registry.members.get("agent")
        if agent is None:
            return
        agent.message_processor.update_notification_message(
            RuntimeMessage(content), source="user_reminder", sort_value=900
        )

    def register(self, lifecycle: Lifecycle):
        """注册到before_message_generation回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)
