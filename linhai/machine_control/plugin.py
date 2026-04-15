from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Optional, Literal, Union
from linhai.agent import Agent
from linhai.agent.lifecycle import Lifecycle
from linhai.base import Message
from linhai.agent.messages import RuntimeMessage
from linhai.registry import Registry

from linhai.tool.base import ToolResultFailed
from .ssh_host.ssh_host import SshMachineControl

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
        agent = self.registry.get_member_typechecked("agent", Agent)
        agent.message_processor.update_notification_message(
            RuntimeMessage(f"当前在{self.machine_control.target_machine}上"),
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
        self._last_heartbeat: dict[str, float] = {}
        self._inflight: set[str] = set()

    async def _before_agent_loop(self, agent: Agent) -> None:
        from linhai.task_supervisor import TaskSupervisor

        ts = self.registry.get_member_typechecked("task_supervisor", TaskSupervisor)
        ts.create_supervised_task("machine_heartbeat", self._heartbeat_loop)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            now = time.monotonic()
            for machine_id in list(self.machine_control.machines.keys()):
                if machine_id == "master_host":
                    continue
                if machine_id in self._inflight:
                    continue

                host = self.machine_control.machines.get(machine_id)
                if not isinstance(host, SshMachineControl):
                    continue

                is_current = machine_id == self.machine_control.target_machine
                interval = (
                    self.CURRENT_MACHINE_INTERVAL
                    if is_current
                    else self.OTHER_MACHINE_INTERVAL
                )
                last = self._last_heartbeat.get(machine_id, 0)
                if now - last < interval:
                    continue

                self._inflight.add(machine_id)
                result = await host.call_tool("ping", {})
                self._inflight.discard(machine_id)
                if not isinstance(result, ToolResultFailed):
                    self._last_heartbeat[machine_id] = time.monotonic()
                    for source_id in self.machine_control.get_source_chain(machine_id):
                        if source_id != "master_host":
                            self._last_heartbeat[source_id] = self._last_heartbeat[
                                machine_id
                            ]

    def register(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_agent_loop.register(self._before_agent_loop)
