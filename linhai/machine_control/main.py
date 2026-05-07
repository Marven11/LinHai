"""MachineControl类，负责管理多个机器控制类并注册工具。"""

import time

from typing import Any, Dict, Optional, TypedDict
from linhai.agent.lifecycle import Lifecycle
from linhai.config import RemoteMachineConfig
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.utils.common import UiNotice
from .protocol import HostControl
from .master_host.master_host import MasterHostControl
from .posix_shell.posix_shell_control import PosixShellControl
from .bash_host.bash_host import BashHostControl
from .plugin import MachineHeartbeatPlugin
from .process import Process, ProcessCreateInfo


class _StoredProcessInfo(TypedDict):
    argv: list[str]
    exit_time: float | None


class _ProcessEntry(TypedDict):
    pid: str
    machine_id: str
    argv: list[str]
    status: str
    returncode: int | None


class MachineControl:
    """机器控制管理器，负责注册工具和切换机器。"""

    def __init__(
        self,
        registry: Registry,
        remote_machines: list[RemoteMachineConfig],
        tmux_terminal: bool = True,
        remote_shell_control: str = "python",
    ):
        self.registry = registry
        self.target_machine = "master_host"
        self.remote_shell_control = remote_shell_control
        self.remote_machines: Dict[str, RemoteMachineConfig] = {
            cfg.name: cfg for cfg in (remote_machines or [])
        }
        self.machines: Dict[str, HostControl] = {
            "master_host": MasterHostControl(registry, tmux_terminal=tmux_terminal),
        }
        self.machine_descriptions: Dict[str, str] = {
            "master_host": "本地主机",
        }
        self.source_machines: Dict[str, str | None] = {
            "master_host": None,
        }
        self._process_infos: Dict[str, _StoredProcessInfo] = {}
        self._saved_machine_info: dict = {}
        registry.register_member("machine_control", self)

    async def switch_machine(
        self, machine_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if machine_id not in self.machines:
            return FailedToolResult(content=f"机器未找到: {machine_id}")

        old_machine_id = self.target_machine
        self.target_machine = machine_id

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"已切换机器: {old_machine_id} -> {machine_id}"
            ),
        )

        return SuccessfulToolResult(
            content=f"已切换机器: {old_machine_id} -> {machine_id}"
        )

    async def disconnect_machine(
        self, machine_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if machine_id not in self.machines:
            return FailedToolResult(content=f"机器未找到: {machine_id}")

        host_control = self.machines[machine_id]
        if isinstance(host_control, MasterHostControl):
            return FailedToolResult(content="不能断开master_host")

        await host_control.disconnect()

        del self.machines[machine_id]
        self.source_machines.pop(machine_id, None)
        self.machine_descriptions.pop(machine_id, None)

        switched = ""
        if self.target_machine == machine_id:
            self.target_machine = "master_host"
            switched = "，已自动切换到机器: master_host"

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(level="INFO", content=f"已断开机器: {machine_id}{switched}"),
        )

        return SuccessfulToolResult(content=f"已断开机器: {machine_id}{switched}")

    async def add_posix_shell_machine(
        self,
        machine_id: str,
        pid: str,
        source_machine: Optional[str] = None,
    ) -> SuccessfulToolResult | FailedToolResult:
        if machine_id in self.machines:
            return FailedToolResult(content=f"机器ID已存在: {machine_id}")

        source_machine_id = source_machine or self.target_machine
        if source_machine_id not in self.machines:
            return FailedToolResult(content=f"源机器不存在: {source_machine_id}")

        source_host = self.machines[source_machine_id]
        process = source_host.get_process(pid)
        if process is None:
            return FailedToolResult(
                content=f"进程不存在: {pid} (在机器 {source_machine_id} 上)"
            )

        if self.remote_shell_control == "bash":
            return await self._connect_bash_control(
                machine_id, process, source_machine_id, pid
            )

        shell_control = PosixShellControl(
            registry=self.registry,
        )

        connected = await shell_control.connect(process)
        if not connected:
            return FailedToolResult(content=f"连接posix shell进程失败: PID {pid}")

        self.machines[machine_id] = shell_control
        shell_control._machine_id = machine_id
        self.source_machines[machine_id] = source_machine_id
        self.machine_descriptions[machine_id] = (
            f"Posix shell进程主机 (PID: {pid}, 来自: {source_machine_id})"
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"Posix shell连接成功: 已连接posix shell进程为机器 {machine_id} (PID: {pid})",
            ),
        )

        return SuccessfulToolResult(
            content=f"已成功连接posix shell进程为机器: {machine_id} (PID: {pid})"
        )

    async def _connect_bash_control(
        self,
        machine_id: str,
        process: Process,
        source_machine_id: str,
        pid: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        bash_control = BashHostControl(registry=self.registry)
        connected = await bash_control.connect(process)
        if not connected:
            return FailedToolResult(content=f"Bash控制连接失败: PID {pid}")

        self.machines[machine_id] = bash_control
        bash_control._machine_id = machine_id
        self.source_machines[machine_id] = source_machine_id
        self.machine_descriptions[machine_id] = (
            f"Bash shell主机 (PID: {pid}, 来自: {source_machine_id})"
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"Bash控制连接成功: 已连接bash shell进程为机器 {machine_id} (PID: {pid})",
            ),
        )

        return SuccessfulToolResult(
            content=f"已成功连接bash shell进程为机器: {machine_id} (PID: {pid})"
        )

    async def connect_remote_config(
        self, name: str
    ) -> SuccessfulToolResult | FailedToolResult:
        if name not in self.remote_machines:
            available = ", ".join(self.remote_machines.keys()) or "无"
            return FailedToolResult(
                content=f"远程机器配置未找到: {name}。可用配置: {available}"
            )
        if name in self.machines:
            return FailedToolResult(content=f"机器ID已存在: {name}")

        config = self.remote_machines[name]

        shell_control = PosixShellControl(registry=self.registry)

        current_host = self.machines[self.target_machine]
        result = await current_host.create_process(config.argv, wait_second=15.0)

        if not result.success:
            return FailedToolResult(content=f"连接远程机器失败: {result.error}")

        if result.returncode is not None:
            return FailedToolResult(
                content=f"连接进程立即退出(code={result.returncode}): {result.stderr}"
            )

        process = current_host.get_process(result.pid)
        if process is None:
            return FailedToolResult(content=f"连接进程不存在: {result.pid}")

        connected = await shell_control.connect(process)
        if not connected:
            await process.kill()
            return FailedToolResult(content=f"连接远程机器失败: {name}")

        self.machines[name] = shell_control
        shell_control._machine_id = name
        self.source_machines[name] = self.target_machine
        desc = config.description or f"远程机器 ({name})"
        self.machine_descriptions[name] = desc

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"远程机器连接成功: {name}",
            ),
        )

        return SuccessfulToolResult(content=f"已成功连接远程机器: {name}")

    async def add_ether_ghost_machine(
        self,
        machine_id: str,
        session_type: str,
        connection_args: Dict[str, Any],
    ) -> SuccessfulToolResult | FailedToolResult:
        if machine_id in self.machines:
            return FailedToolResult(content=f"机器ID已存在: {machine_id}")

        from .ether_ghost_host.ether_ghost_host import EtherGhostMachineControl

        ether_control = EtherGhostMachineControl(
            session_type=session_type,
            connection_args=connection_args,
            machine_id=machine_id,
        )
        await ether_control.initialize()

        self.machines[machine_id] = ether_control
        self.source_machines[machine_id] = None
        self.machine_descriptions[machine_id] = (
            f"EtherGhost webshell主机 (类型: {session_type})"
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"EtherGhost连接成功: 已连接到远程机器 {machine_id} (session类型: {session_type})",
            ),
        )

        return SuccessfulToolResult(
            content=f"已成功添加EtherGhost机器: {machine_id} (session类型: {session_type})"
        )

    async def list_all_terminals(self) -> SuccessfulToolResult | FailedToolResult:
        """列出所有机器上的所有终端"""
        all_terminals = []
        for machine_id, host_control in self.machines.items():
            result = await host_control.get_terminals()
            if isinstance(result, FailedToolResult):
                return FailedToolResult(
                    content=f"获取机器 {machine_id} 的终端列表失败: {result.content}"
                )

            if result.content:
                all_terminals.append(f"机器 {machine_id}:\n{result.content}")

        if not all_terminals:
            content = "当前所有机器上都没有终端"
        else:
            content = "\n\n".join(all_terminals)

        return SuccessfulToolResult(content=content)

    async def list_machines(self) -> SuccessfulToolResult:
        lines = ["可用机器:"]
        for machine_id, description in self.machine_descriptions.items():
            current = " (当前)" if machine_id == self.target_machine else ""
            lines.append(f"  - {machine_id}: {description}{current}")

        return SuccessfulToolResult(content="\n".join(lines))

    async def transfer_file(
        self,
        from_filepath: str,
        from_machine: str,
        to_filepath: str,
        to_machine: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        """将文件从一台机器传输到另一台机器。

        Args:
            from_filepath: 源文件路径
            from_machine: 源机器ID
            to_filepath: 目标文件路径
            to_machine: 目标机器ID

        Returns:
            执行结果
        """
        try:
            import tempfile
            import os

            if from_machine == to_machine:
                return FailedToolResult(content=f"源机器和目标机器相同: {from_machine}")

            if from_machine not in self.machines:
                return FailedToolResult(content=f"源机器不存在: {from_machine}")
            if to_machine not in self.machines:
                return FailedToolResult(content=f"目标机器不存在: {to_machine}")

            from_control = self.machines[from_machine]
            to_control = self.machines[to_machine]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".transfer") as tmp:
                temp_path = tmp.name

            try:
                if hasattr(from_control, "download_file_concurrent"):
                    download_result = await from_control.download_file_concurrent(
                        from_filepath, temp_path
                    )
                else:
                    download_result = FailedToolResult(
                        content=f"源机器 {from_machine} 不支持文件下载"
                    )

                if isinstance(download_result, FailedToolResult):
                    return FailedToolResult(
                        content=f"从源机器下载文件失败: {download_result.content}"
                    )

                with open(temp_path, "rb") as f:
                    file_data = f.read()

                if hasattr(to_control, "upload_file_concurrent"):
                    upload_result = await to_control.upload_file_concurrent(
                        file_data, to_filepath
                    )
                else:
                    upload_result = FailedToolResult(
                        content=f"目标机器 {to_machine} 不支持文件上传"
                    )

                if isinstance(upload_result, FailedToolResult):
                    return FailedToolResult(
                        content=f"向目标机器上传文件失败: {upload_result.content}"
                    )

                return SuccessfulToolResult(
                    content=f"文件传输成功: {from_machine}:{from_filepath} -> {to_machine}:{to_filepath}"
                )

            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            return FailedToolResult(content=f"文件传输失败: {e}")

    def get_source_chain(self, machine_id: str) -> list[str]:
        chain: list[str] = []
        visited: set[str] = set()
        current = self.source_machines.get(machine_id)
        while current is not None and current not in visited:
            visited.add(current)
            chain.append(current)
            current = self.source_machines.get(current)
        return chain

    _EXIT_CLEANUP_SECONDS = 300.0

    def store_process_info(self, pid: str, machine_id: str, argv: list[str]) -> None:
        self._process_infos[f"{machine_id}:{pid}"] = {"argv": argv, "exit_time": None}

    def list_processes(self) -> list[_ProcessEntry]:
        now = time.monotonic()
        result: list[_ProcessEntry] = []
        for machine_id, host_control in self.machines.items():
            for pid in host_control.list_process_pids():
                key = f"{machine_id}:{pid}"
                info = self._process_infos.get(key)
                process = host_control.get_process(pid)
                if process is not None:
                    returncode = process.returncode
                    status = "exited" if returncode is not None else "running"
                else:
                    returncode = None
                    status = "error"
                if (
                    info is not None
                    and returncode is not None
                    and info["exit_time"] is None
                ):
                    info["exit_time"] = now
                if info is not None and info["exit_time"] is not None:
                    if now - info["exit_time"] > self._EXIT_CLEANUP_SECONDS:
                        continue
                result.append(
                    {
                        "pid": pid,
                        "machine_id": machine_id,
                        "argv": info["argv"] if info else [],
                        "status": status,
                        "returncode": returncode,
                    }
                )
        return result

    def serialize(self) -> dict:
        machines = {}
        for machine_id in list(self.machine_descriptions.keys()):
            if machine_id == "master_host":
                continue
            argv = []
            for key, info in self._process_infos.items():
                if key.startswith(f"{machine_id}:"):
                    argv = info["argv"]
                    break
            machines[machine_id] = {
                "description": self.machine_descriptions.get(machine_id, ""),
                "source_machine": self.source_machines.get(machine_id),
                "argv": argv,
            }
        return {"machines": machines}

    def restore_from(self, data: dict) -> None:
        self._saved_machine_info = data.get("machines", {})
        master = self.machines.get("master_host")
        self.machines = {"master_host": master} if master else {}
        self.machine_descriptions = {"master_host": "本地主机"}
        self.source_machines = {"master_host": None}
        self.target_machine = "master_host"
        self._process_infos = {}

    def register_plugin(self, lifecycle: "Lifecycle"):
        """注册插件到lifecycle。"""
        heartbeat_plugin = MachineHeartbeatPlugin(self.registry, self)
        heartbeat_plugin.register(lifecycle)
        lifecycle.after_conversation_restore.register(self._after_conversation_restore)

        async def _on_process_create(info: "ProcessCreateInfo") -> None:
            self.store_process_info(info.process.pid, info.machine_id, info.argv)

        lifecycle.after_process_create.register(_on_process_create)

    async def _after_conversation_restore(self) -> None:
        if not self._saved_machine_info:
            return

        from linhai.agent.messages import RuntimeMessage
        from linhai.agent.message import AgentMessage

        lines = ["conversation恢复：以下远程机器在保存时已连接，现已断开:"]
        for machine_id, info in self._saved_machine_info.items():
            desc = info.get("description", "unknown")
            argv = info.get("argv", [])
            argv_str = " ".join(argv) if argv else "unknown"
            lines.append(f"  - {machine_id}: {desc}, 启动参数={argv_str}")

        agent_message = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        agent_message.update_notification_message(
            RuntimeMessage("\n".join(lines)),
            source="machine_disconnected",
            sort_value=0,
        )
        self._saved_machine_info = {}
