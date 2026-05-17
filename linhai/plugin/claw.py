import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry
from linhai.plugin.message_checkers import Plugin
from linhai.prompt import (
    AGENTS_MD,
    BOOTSTRAP_MD,
    IDENTITY_MD,
    REMINDER_MD,
    SOUL_MD,
    USER_MD,
)
from .reminder import ReminderPlugin, ReminderWriteGuardPlugin

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent


class ClawPlugin(Plugin):
    """CLAW模式插件：在启用--claw时添加系统提示和固定消息。"""

    def __init__(self, registry: Registry, claw_folder: Optional[Path] = None):
        super().__init__(registry)
        if claw_folder is not None:
            self.claw_dir = claw_folder.expanduser()
        else:
            self.claw_dir = Path.home() / ".local" / "share" / "linhai" / "claw"
        self.reminder_plugin = ReminderPlugin(registry, self.claw_dir)
        self.write_guard_plugin = ReminderWriteGuardPlugin(registry, self.claw_dir)

    async def before_agent_loop(self, agent: "linhai_agent") -> None:
        """在agent循环开始前添加CLAW模式介绍和文档内容。"""
        # 插件只在cli_args.claw为True时注册，因此无需再次检查
        if not self.claw_dir.exists():
            self._initialize_claw_files()
            return

        # 添加CLAW模式介绍到pinned messages
        claw_intro = f"""## CLAW模式介绍

你正在以Continuous Living Autonomous Worker模式运行。这个模式下，你有五个核心文档来维护你的身份和记忆：

1. **AGENTS.md** - 你的工作空间和操作指南
2. **BOOTSTRAP.md** - 初始引导文档（首次运行后删除）
3. **IDENTITY.md** - 你的身份定义
4. **SOUL.md** - 你的核心原则和风格
5. **USER.md** - 关于你帮助的人类信息
6. **REMINDER.md** - 一句极为简短的提醒，包含最经常出错的教训

这些文档位于: {self.claw_dir}

每次会话开始时，你应该阅读这些文档以维持连续性。"""

        await agent.message_processor.add_pinned_message(RuntimeMessage(claw_intro))

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
                formatted = (
                    "<<file_content>>\n<<message>>"
                    "以下是文件的完整内容，不要重复读取！<<message>>"
                    f"<<filepath>>{str(file_path)!r}<<filepath>>\n"
                    f"<<content>>{content}<<content>>\n"
                    "<<file_content>>"
                )
                await agent.message_processor.add_pinned_message(
                    RuntimeMessage(formatted)
                )

    def _initialize_claw_files(self) -> None:
        """从prompt.py常量读取初始内容并写入claw目录的所有文件。"""
        self.claw_dir.mkdir(parents=True, exist_ok=True)

        files = [
            ("AGENTS.md", AGENTS_MD),
            ("BOOTSTRAP.md", BOOTSTRAP_MD),
            ("IDENTITY.md", IDENTITY_MD),
            ("REMINDER.md", REMINDER_MD),
            ("SOUL.md", SOUL_MD),
            ("USER.md", USER_MD),
        ]

        for filename, content in files:
            (self.claw_dir / filename).write_text(content, encoding="utf-8")

    def register(self, lifecycle: Lifecycle):
        self.reminder_plugin.register(lifecycle)
        self.write_guard_plugin.register(lifecycle)
        lifecycle.before_agent_loop.register(self.before_agent_loop)


class ClawHeartbeatPlugin(Plugin):
    """CLAW模式心跳插件：当agent等待用户超过指定时间后自动唤醒。"""

    def __init__(self, registry: Registry, heartbeat_interval: int):
        super().__init__(registry)
        self.heartbeat_interval = heartbeat_interval
        self._next_reminder_time: float = 0.0

    async def before_agent_loop(self, agent: "linhai_agent") -> None:
        from linhai.task_supervisor import TaskSupervisor

        self._next_reminder_time = time.monotonic() + self.heartbeat_interval
        ts = self.registry.get_member_typechecked("task_supervisor", TaskSupervisor)
        ts.create_supervised_task("claw_heartbeat", lambda: self._heartbeat_loop(agent))

    async def before_message_generation(self) -> None:
        self._next_reminder_time = time.monotonic() + self.heartbeat_interval

    async def _heartbeat_loop(self, agent: "linhai_agent") -> None:
        while True:
            remaining = self._next_reminder_time - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            if time.monotonic() < self._next_reminder_time:
                continue
            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            if state_machine.state != "waiting_user":
                self._next_reminder_time = time.monotonic() + self.heartbeat_interval
                continue
            state_machine.transition_to_working()
            minutes = self.heartbeat_interval // 60
            await agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"{minutes}分钟过去了，用户仍然没有回复。"
                    "你应该诚实地更新claw记忆等文档，记录当前状态，"
                    "重新诚实地反思用户交代的任务是否真正完成"
                )
            )
            self._next_reminder_time = time.monotonic() + self.heartbeat_interval

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_agent_loop.register(self.before_agent_loop)
        lifecycle.before_message_generation.register(self.before_message_generation)
