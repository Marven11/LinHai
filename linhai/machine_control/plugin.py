from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Optional, Literal, Union
from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.base import Message
from linhai.agent.messages import RuntimeMessage
from linhai.registry import Registry
from linhai.utils.i18n import t

from linhai.tool.base import ToolResultFailed

if TYPE_CHECKING:
    from .main import MachineControl


class MachineControlPlugin:
    """MachineControl的插件，用于添加当前机器提示。"""

    def __init__(self, registry: Registry, machine_control: MachineControl):
        self.registry = registry
        self.machine_control = machine_control

    async def before_message_generation(self):
        """在消息生成前更新notification_message。"""
        if len(self.machine_control.machines) <= 1:
            return
        agent = self.registry.get_member_typechecked("agent", Agent)
        agent.message_processor.update_notification_message(
            RuntimeMessage(
                t(
                    {
                        "zh_CN": f"当前在{self.machine_control.target_machine}上",
                        "en": f"Currently on {self.machine_control.target_machine}",
                    }
                )
            ),
            source="machine_control",
            sort_value=0,
        )

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        return None

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.before_message_generation.register(self.before_message_generation)
        lifecycle.after_toolcall.register(self.after_toolcall)


class MachineHeartbeatPlugin:
    """多跳机器控制heartbeat插件，定期发送ping保持连接活跃。"""

    CURRENT_MACHINE_INTERVAL = 5.0
    OTHER_MACHINE_INTERVAL = 30.0

    def __init__(self, registry: Registry, machine_control: MachineControl):
        self.registry = registry
        self.machine_control = machine_control
        self._next_heartbeat: dict[str, float] = {}

    def _get_interval(self, machine_id: str) -> float:
        if machine_id == self.machine_control.target_machine:
            return self.CURRENT_MACHINE_INTERVAL
        return self.OTHER_MACHINE_INTERVAL

    def _pick_earliest_due(self, now: float) -> str | None:
        due = {mid: t for mid, t in self._next_heartbeat.items() if t <= now}
        if not due:
            return None
        return min(due, key=lambda mid: due[mid])

    async def _before_agent_loop(self, agent: Agent) -> None:
        from linhai.task_supervisor import TaskSupervisor

        ts = self.registry.get_member_typechecked("task_supervisor", TaskSupervisor)
        ts.create_supervised_task("machine_heartbeat", self._heartbeat_loop)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            now = time.monotonic()

            new_machines = {
                mid: now
                for mid in self.machine_control.machines
                if mid != "master_host" and mid not in self._next_heartbeat
            }
            self._next_heartbeat.update(new_machines)

            earliest_id = self._pick_earliest_due(now)
            if earliest_id is None:
                continue

            host = self.machine_control.machines.get(earliest_id)
            if host is None:
                del self._next_heartbeat[earliest_id]
                continue

            result = await host.ping()
            interval = self._get_interval(earliest_id)
            next_time = time.monotonic() + interval

            if not isinstance(result, ToolResultFailed):
                self._next_heartbeat[earliest_id] = next_time
                for source_id in self.machine_control.get_source_chain(earliest_id):
                    if source_id != "master_host" and source_id in self._next_heartbeat:
                        source_next = time.monotonic() + self._get_interval(source_id)
                        self._next_heartbeat[source_id] = max(
                            self._next_heartbeat[source_id], source_next
                        )
            else:
                self._next_heartbeat[earliest_id] = next_time

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_agent_loop.register(self._before_agent_loop)
