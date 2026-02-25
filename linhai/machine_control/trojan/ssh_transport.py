import asyncio
import tempfile
import base64
from asyncio.subprocess import Process
from pathlib import Path
from typing import Dict, Any, Optional

from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice
from .transport import TrojanTransport


class SshTrojanTransport:
    def __init__(
        self,
        host: str,
        group_chat: GroupChat,
        port: int = 22,
        username: Optional[str] = None,
    ):
        if username is None:
            import getpass

            username = getpass.getuser()

        self.host = host
        self.port = port
        self.username = username
        self.group_chat = group_chat
        self.trojan_path: Optional[Path] = None
        self.remote_trojan_path: Optional[str] = None
        self._trojan_transport: Optional[TrojanTransport] = None

    async def _check_python_version(self, ssh_cmd: list[str]) -> bool:
        check_cmd = ssh_cmd + ["/usr/bin/env python3 -V"]
        process = await asyncio.create_subprocess_exec(
            *check_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit = 256 * 1024
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"检查远程Python版本失败: {error_msg}"
                ),
            )
            return False
        return True

    async def _copy_trojan_to_remote(self, ssh_cmd: list[str]) -> str:
        if self.trojan_path is None or not self.trojan_path.exists():
            raise FileNotFoundError("本地trojan临时文件不存在")

        trojan_content = self.trojan_path.read_text(encoding="utf-8")

        remote_temp_path_cmd = ssh_cmd + ["mktemp --suffix=.py"]
        process = await asyncio.create_subprocess_exec(
            *remote_temp_path_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"创建远程临时文件失败: {error_msg}"
                ),
            )
            raise RuntimeError(f"创建远程临时文件失败: {error_msg}")

        remote_path = stdout.decode().strip()

        encoded_content = base64.b64encode(trojan_content.encode()).decode()
        echo_cmd = ssh_cmd + [f"echo {encoded_content} | base64 -d > {remote_path}"]
        process = await asyncio.create_subprocess_exec(
            *echo_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"写入远程文件失败: {error_msg}"
                ),
            )
            cleanup_cmd = ssh_cmd + [f"rm -f {remote_path}"]
            cleanup_process = await asyncio.create_subprocess_exec(
                *cleanup_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(cleanup_process.wait(), timeout=60.0)
            raise RuntimeError(f"写入远程文件失败: {error_msg}")

        return remote_path

    async def _start_trojan_process(
        self, ssh_cmd: list[str], remote_trojan_path: str
    ) -> Optional[Process]:
        ssh_trojan_cmd = ssh_cmd + [f"/usr/bin/env python3 {remote_trojan_path}"]
        process = await asyncio.create_subprocess_exec(
            *ssh_trojan_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.sleep(1)
        return process

    async def connect(self) -> bool:
        ssh_cmd = [
            "ssh",
            f"{self.username}@{self.host}",
            "-p",
            str(self.port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
        ]

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"开始连接SSH服务器: {self.host}:{self.port}"
            ),
        )

        self.trojan_path = Path(tempfile.mktemp(suffix=".py"))
        trojan_file_path = Path(__file__).parent / "trojan.py"
        if not trojan_file_path.exists():
            raise FileNotFoundError(f"trojan.py文件不存在: {trojan_file_path}")
        trojan_content = trojan_file_path.read_text(encoding="utf-8")
        self.trojan_path.write_text(trojan_content, encoding="utf-8")

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"检查远程机器Python版本: {self.host}:{self.port}",
            ),
        )

        if not await self._check_python_version(ssh_cmd):
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"远程机器Python版本检查失败: {self.host}:{self.port}",
                ),
            )
            if self.trojan_path and self.trojan_path.exists():
                self.trojan_path.unlink(missing_ok=True)
            return False

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"Python版本检查通过: {self.host}:{self.port}"
            ),
        )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"复制控制程序到远程机器: {self.host}:{self.port}",
            ),
        )

        remote_trojan_path = await self._copy_trojan_to_remote(ssh_cmd)
        self.remote_trojan_path = remote_trojan_path

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"控制程序已复制到远程机器: {self.host}:{self.port}",
            ),
        )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"启动远程控制程序: {self.host}:{self.port}"
            ),
        )

        process = await self._start_trojan_process(ssh_cmd, remote_trojan_path)
        if (
            process is None
            or process.stdin is None
            or process.stdout is None
            or process.stderr is None
        ):
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"启动远程控制程序失败: {self.host}:{self.port}",
                ),
            )
            if self.trojan_path and self.trojan_path.exists():
                self.trojan_path.unlink(missing_ok=True)
            return False

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"远程控制程序启动成功: {self.host}:{self.port}",
            ),
        )

        self._trojan_transport = TrojanTransport(
            group_chat=self.group_chat,
            stdin=process.stdin,
            stdout=process.stdout,
            stderr=process.stderr,
            process=process,
        )
        self._trojan_transport.start_reading()
        return True

    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._trojan_transport is None:
            raise ConnectionError("未建立连接")
        return await self._trojan_transport.send_request(method, params)

    async def disconnect(self):
        if self._trojan_transport:
            await self._trojan_transport.disconnect()

        if self.trojan_path and self.trojan_path.exists():
            self.trojan_path.unlink(missing_ok=True)

        self._trojan_transport = None

    def is_connected(self) -> bool:
        return (
            self._trojan_transport is not None and self._trojan_transport.is_connected()
        )

    async def wait_for_disconnect(self):
        if self._trojan_transport:
            await self._trojan_transport.wait_for_disconnect()
