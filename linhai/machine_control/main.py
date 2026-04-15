"""MachineControl类，负责管理多个机器控制类并注册工具。"""

from typing import Dict, Optional, Any
from linhai.agent.lifecycle import Lifecycle
from linhai.registry import Registry
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils.common import UiNotice
from .protocol import HostControl
from .master_host.master_host import MasterHostControl
from .ssh_host.ssh_host import SshMachineControl
from .plugin import MachineControlPlugin, MachineHeartbeatPlugin


class MachineControl:
    """机器控制管理器，负责注册工具和切换机器。"""

    def __init__(self, registry: Registry, tmux_terminal: bool = True):
        self.registry = registry
        self.target_machine = "master_host"
        self.machines: Dict[str, HostControl] = {
            "master_host": MasterHostControl(registry, tmux_terminal=tmux_terminal),
        }
        self.machine_descriptions: Dict[str, str] = {
            "master_host": "本地主机",
        }
        self.source_machines: Dict[str, str | None] = {
            "master_host": None,
        }
        registry.register_member("machine_control", self)

    async def switch_machine(
        self, machine_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id not in self.machines:
            return ToolResultFailed(content=f"机器未找到: {machine_id}")

        old_machine_id = self.target_machine
        self.target_machine = machine_id

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO", content=f"已切换机器: {old_machine_id} -> {machine_id}"
            ),
        )

        return ToolResultSuccess(content=f"已切换到机器: {machine_id}")

    async def add_bash_machine(
        self,
        machine_id: str,
        pid: str,
        source_machine: Optional[str] = None,
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id in self.machines:
            return ToolResultFailed(content=f"机器ID已存在: {machine_id}")

        source_machine_id = source_machine or self.target_machine
        if source_machine_id not in self.machines:
            return ToolResultFailed(content=f"源机器不存在: {source_machine_id}")

        source_host = self.machines[source_machine_id]
        process = source_host.get_process(pid)
        if process is None:
            return ToolResultFailed(
                content=f"进程不存在: {pid} (在机器 {source_machine_id} 上)"
            )

        bash_control = SshMachineControl(
            registry=self.registry,
        )

        connected = await bash_control.connect(process)
        if not connected:
            return ToolResultFailed(content=f"连接bash进程失败: PID {pid}")

        self.machines[machine_id] = bash_control
        self.source_machines[machine_id] = source_machine_id
        self.machine_descriptions[machine_id] = (
            f"Bash进程主机 (PID: {pid}, 来自: {source_machine_id})"
        )

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"Bash连接成功: 已连接bash进程为机器 {machine_id} (PID: {pid})",
            ),
        )

        return ToolResultSuccess(
            content=f"已成功连接bash进程为机器: {machine_id} (PID: {pid})"
        )

    async def add_ssh_machine(
        self,
        machine_id: str,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id in self.machines:
            return ToolResultFailed(content=f"机器ID已存在: {machine_id}")

        ssh_control = SshMachineControl(
            registry=self.registry, host=host, port=port, username=username
        )

        ssh_cmd = [
            "ssh",
            f"{username or 'root'}@{host}",
            "-p",
            str(port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "bash",
            "-s",
        ]

        current_host = self.machines[self.target_machine]
        result = await current_host.create_process(ssh_cmd, wait_second=15.0)

        if not result.success:
            return ToolResultFailed(content=f"连接SSH机器失败: {result.error}")

        if result.returncode is not None:
            return ToolResultFailed(
                content=f"SSH进程立即退出(code={result.returncode}): {result.stderr}"
            )

        process = current_host.get_process(result.pid)
        if process is None:
            return ToolResultFailed(content=f"SSH进程不存在: {result.pid}")

        connected = await ssh_control.connect(process)
        if not connected:
            await process.kill()
            return ToolResultFailed(content=f"连接SSH机器失败: {host}:{port}")

        self.machines[machine_id] = ssh_control
        self.source_machines[machine_id] = self.target_machine
        self.machine_descriptions[machine_id] = f"SSH远程主机 ({host}:{port})"

        await self.registry.send_if_exists(
            "ui_log",
            UiNotice(
                level="INFO",
                content=f"SSH连接成功: 已连接到远程机器 {machine_id} ({host}:{port}), 用户名 {username}",
            ),
        )

        return ToolResultSuccess(
            content=f"已成功添加SSH机器: {machine_id} ({host}:{port})"
        )

    async def add_ether_ghost_machine(
        self,
        machine_id: str,
        session_type: str,
        connection_args: Dict[str, Any],
    ) -> ToolResultSuccess | ToolResultFailed:
        if machine_id in self.machines:
            return ToolResultFailed(content=f"机器ID已存在: {machine_id}")

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

        return ToolResultSuccess(
            content=f"已成功添加EtherGhost机器: {machine_id} (session类型: {session_type})"
        )

    async def list_all_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        """列出所有机器上的所有终端"""
        all_terminals = []
        for machine_id, host_control in self.machines.items():
            result = await host_control.get_terminals()
            if isinstance(result, ToolResultFailed):
                return ToolResultFailed(
                    content=f"获取机器 {machine_id} 的终端列表失败: {result.content}"
                )

            if result.content:
                all_terminals.append(f"机器 {machine_id}:\n{result.content}")

        if not all_terminals:
            content = "当前所有机器上都没有终端"
        else:
            content = "\n\n".join(all_terminals)

        return ToolResultSuccess(content=content)

    async def list_machines(self) -> ToolResultSuccess:
        lines = ["可用机器:"]
        for machine_id, description in self.machine_descriptions.items():
            current = " (当前)" if machine_id == self.target_machine else ""
            lines.append(f"  - {machine_id}: {description}{current}")

        return ToolResultSuccess(content="\n".join(lines))

    async def transfer_file(
        self,
        from_filepath: str,
        from_machine: str,
        to_filepath: str,
        to_machine: str,
    ) -> ToolResultSuccess | ToolResultFailed:
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
                return ToolResultFailed(content=f"源机器和目标机器相同: {from_machine}")

            if from_machine not in self.machines:
                return ToolResultFailed(content=f"源机器不存在: {from_machine}")
            if to_machine not in self.machines:
                return ToolResultFailed(content=f"目标机器不存在: {to_machine}")

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
                    download_result = ToolResultFailed(
                        content=f"源机器 {from_machine} 不支持文件下载"
                    )

                if isinstance(download_result, ToolResultFailed):
                    return ToolResultFailed(
                        content=f"从源机器下载文件失败: {download_result.content}"
                    )

                with open(temp_path, "rb") as f:
                    file_data = f.read()

                if hasattr(to_control, "upload_file_concurrent"):
                    upload_result = await to_control.upload_file_concurrent(
                        file_data, to_filepath
                    )
                else:
                    upload_result = ToolResultFailed(
                        content=f"目标机器 {to_machine} 不支持文件上传"
                    )

                if isinstance(upload_result, ToolResultFailed):
                    return ToolResultFailed(
                        content=f"向目标机器上传文件失败: {upload_result.content}"
                    )

                return ToolResultSuccess(
                    content=f"文件传输成功: {from_machine}:{from_filepath} -> {to_machine}:{to_filepath}"
                )

            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        except Exception as e:
            return ToolResultFailed(content=f"文件传输失败: {e}")

    def get_source_chain(self, machine_id: str) -> list[str]:
        chain: list[str] = []
        visited: set[str] = set()
        current = self.source_machines.get(machine_id)
        while current is not None and current not in visited:
            visited.add(current)
            chain.append(current)
            current = self.source_machines.get(current)
        return chain

    def register_plugin(self, lifecycle: "Lifecycle"):
        """注册插件到lifecycle。"""
        plugin = MachineControlPlugin(self.registry, self)
        plugin.register(lifecycle)
        heartbeat_plugin = MachineHeartbeatPlugin(self.registry, self)
        heartbeat_plugin.register(lifecycle)
