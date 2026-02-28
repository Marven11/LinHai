from pathlib import Path
from typing import TYPE_CHECKING

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.base import RuntimeMessage, FileContentMessage
from linhai.group_chat import GroupChat
from linhai.plugin.message_checkers import Plugin

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class ClawPlugin(Plugin):
    """CLAW模式插件：在启用--claw时添加系统提示和固定消息。"""

    def __init__(self, group_chat: GroupChat, cli_args):
        super().__init__(group_chat)
        self.cli_args = cli_args
        self.claw_dir = Path.home() / ".local" / "share" / "linhai" / "claw"

    async def before_agent_loop(self, agent: "linhai_agent") -> None:
        """在agent循环开始前添加CLAW模式介绍和文档内容。"""
        # 插件只在cli_args.claw为True时注册，因此无需再次检查
        if not self.claw_dir.exists():
            return

        # 添加CLAW模式介绍到pinned messages
        claw_intro = f"""## CLAW模式介绍

你正在以Continuous Living Autonomous Worker模式运行。这个模式下，你有五个核心文档来维护你的身份和记忆：

1. **AGENTS.md** - 你的工作空间和操作指南
2. **BOOTSTRAP.md** - 初始引导文档（首次运行后删除）
3. **IDENTITY.md** - 你的身份定义
4. **SOUL.md** - 你的核心原则和风格
5. **USER.md** - 关于你帮助的人类信息

这些文档位于: {self.claw_dir}

每次会话开始时，你应该阅读这些文档以维持连续性。"""

        await agent.message_processor.add_new_message(RuntimeMessage(claw_intro))

        core_files = [
            "AGENTS.md",
            "BOOTSTRAP.md",
            "IDENTITY.md",
            "SOUL.md",
            "USER.md",
        ]

        for filename in core_files:
            file_path = self.claw_dir / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8").strip()
                await agent.message_processor.add_new_message(
                    FileContentMessage(
                        filepath=str(file_path),
                        content=content,
                        show_line_numbers=False,
                    )
                )

    def register(self, lifecycle: Lifecycle):
        lifecycle.register_before_agent_loop(self.before_agent_loop)
