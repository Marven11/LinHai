import asyncio
import difflib
import os
from pathlib import Path
from typing import TYPE_CHECKING

from linhai.agent.lifecycle import Lifecycle
from linhai.agent.messages import RuntimeMessage
from linhai.agent.state_machine import AgentStateMachine
from linhai.registry import Registry
from linhai.plugin.message_checkers import Plugin
from linhai.utils.common import UiNotice

if TYPE_CHECKING:
    from linhai.agent.main import Agent


class InterlinkPlugin(Plugin):
    """Interlink communication plugin: multiple agents communicate via shared file."""

    def __init__(self, registry: Registry, interlink_name: str):
        super().__init__(registry)
        self.interlink_name = interlink_name
        self.base_dir = Path.home() / ".local" / "share" / "linhai" / "interlink"
        self.interlink_dir = self.base_dir / interlink_name
        self.interlink_file = self.interlink_dir / "INTERLINK.txt"
        self.agent_id = "@" + os.urandom(2).hex()
        self._old_content = ""

    async def before_agent_loop(self, agent: "Agent") -> None:
        self.interlink_dir.mkdir(parents=True, exist_ok=True)
        if not self.interlink_file.exists():
            self.interlink_file.touch()

        self._old_content = self.interlink_file.read_text(encoding="utf-8")

        from linhai.base import SystemMessage

        system_message = self.registry.get_member_typechecked(
            "system_message", SystemMessage
        )
        system_message.add_introduction(
            "INTERLINK",
            "# 介绍\n\n"
            "你被加入到一个Agent互联组中，你需要通过用户给定的INTERLINK.txt文件和INTERLINK名称与其他agent通信\n\n"
            "这意味着当前任务需要你和其他agent一起完成\n\n"
            "简单来说，你和其他agent一起通过编辑给定的INTERLINK.txt互相交流，规则如下：\n\n"
            "你可以在INTERLINK.txt中添加任何内容，添加的内容会被自动推送给其他agent，"
            "同时其他agent添加的内容也会被实时推送给你\n\n"
            "如果需要等待INTERLINK.txt被添加新内容，只需要循环sleep 5分钟。"
            "如果有新内容runtime会自动唤醒你并将新内容发送给你\n\n"
            "你应该在INTERLINK.txt中编写消息，消息内容应该以@xxx开头，其中@xxx是用户给你的INTERLINK名称",
        )

        abs_path = self.interlink_file.resolve()
        await agent.message_processor.add_new_message(
            RuntimeMessage(
                f"在{abs_path}中使用ID {self.agent_id}代表自己写入消息和其他agent通信"
            )
        )

        from linhai.task_supervisor import TaskSupervisor

        ts = self.registry.get_member_typechecked("task_supervisor", TaskSupervisor)
        ts.create_supervised_task(
            "interlink_monitor", lambda: self._monitor_loop(agent)
        )

    async def before_message_generation(self) -> None:
        if not self.interlink_file.exists():
            return

        new_content = self.interlink_file.read_text(encoding="utf-8")
        if new_content == self._old_content:
            return

        old_lines = self._old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="INTERLINK.txt (old)",
                tofile="INTERLINK.txt (new)",
                lineterm="",
            )
        )

        if not diff_lines:
            self._old_content = new_content
            return

        diff_text = "\n".join(diff_lines)

        from linhai.agent.main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        await agent.message_processor.add_new_message(
            RuntimeMessage(f"INTERLINK.txt has new messages:\n{diff_text}")
        )
        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content="INTERLINK.txt has new messages"),
        )

        self._old_content = new_content

    async def _monitor_loop(self, agent: "Agent") -> None:
        while True:
            await asyncio.sleep(60)

            if not self.interlink_file.exists():
                continue

            new_content = self.interlink_file.read_text(encoding="utf-8")
            if new_content == self._old_content:
                continue

            state_machine = self.registry.get_member_typechecked(
                "state_machine", AgentStateMachine
            )
            if state_machine.state in ("waiting_user", "sleeping"):
                state_machine.transition_to_working()

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_agent_loop.register(self.before_agent_loop)
        lifecycle.before_message_generation.register(self.before_message_generation)
