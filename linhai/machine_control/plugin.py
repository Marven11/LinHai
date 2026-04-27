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
    """MachineControl的插件，用于添加当前机器提示和on_machine使用警告。"""

    def __init__(self, registry: Registry, machine_control: MachineControl):
        self.registry = registry
        self.machine_control = machine_control
        self.consecutive_same_on_machine_count = 0
        self.last_on_machine: Optional[str] = None

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
        """处理工具调用的结果，合并了原来的before_tool_call和after_tool_call功能。"""
        from linhai.utils.common import UiNotice

        if status == "skipped":

            if "on_machine" in toolcall_arguments:
                on_machine = toolcall_arguments["on_machine"]
                if on_machine is not None:
                    current_machine = self.machine_control.target_machine
                    if on_machine != current_machine:
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="INFO",
                                content=f"正在切换到机器 {on_machine} 执行工具 {tool_name}",
                            ),
                        )
            return None

        elif status == "success":

            if "on_machine" in toolcall_arguments:
                on_machine = toolcall_arguments["on_machine"]
                current_machine = self.machine_control.target_machine

                if on_machine is None or on_machine != current_machine:

                    self.consecutive_same_on_machine_count = 0
                    self.last_on_machine = None
                else:

                    if self.last_on_machine == on_machine:
                        self.consecutive_same_on_machine_count += 1
                    else:
                        self.consecutive_same_on_machine_count = 1
                        self.last_on_machine = on_machine

                    if self.consecutive_same_on_machine_count >= 3:
                        await self.registry.send_if_exists(
                            "ui_log",
                            UiNotice(
                                level="WARNING",
                                content=f"连续{self.consecutive_same_on_machine_count}次工具调用都指定了相同的on_machine '{on_machine}'，且未切换机器。请确认是否需要频繁指定。",
                            ),
                        )
            return None

        else:
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
