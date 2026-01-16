"""SSH机器控制类，用于通过SSH连接远程机器并执行工具。"""

from typing import Dict, Optional, Any
import asyncio
import json
import tempfile
from pathlib import Path

from linhai.group_chat import GroupChat
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils import CliRuntimeNotice


class SshMachineControl:
    """SSH机器控制类，负责通过SSH连接远程机器并调用工具。"""

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
        self.trojan_path = None
        self.remote_trojan_path = None
        self.process = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.request_id = 0

    async def _check_python_version(self, ssh_cmd: list[str]) -> bool:
        """检查远程机器上的Python版本。"""
        check_cmd = ssh_cmd + ["/usr/bin/env python3 -V"]
        process = await asyncio.create_subprocess_exec(
            *check_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"检查远程Python版本失败: {error_msg}"
                ),
            )
            return False
        return True

    async def _copy_trojan_to_remote(self, ssh_cmd: list[str]) -> str:
        """将trojan.py复制到远程机器，返回远程临时文件路径。"""
        if self.trojan_path is None or not self.trojan_path.exists():
            raise FileNotFoundError("本地trojan临时文件不存在")

        trojan_content = self.trojan_path.read_text(encoding="utf-8")  # pylint: disable=unspecified-encoding

        remote_temp_path_cmd = ssh_cmd + ["mktemp --suffix=.py"]
        process = await asyncio.create_subprocess_exec(
            *remote_temp_path_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"创建远程临时文件失败: {error_msg}"
                ),
            )
            raise RuntimeError(f"创建远程临时文件失败: {error_msg}")

        remote_path = stdout.decode().strip()

        import base64

        encoded_content = base64.b64encode(trojan_content.encode()).decode()
        echo_cmd = ssh_cmd + [f"echo {encoded_content} | base64 -d > {remote_path}"]
        process = await asyncio.create_subprocess_exec(
            *echo_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"写入远程文件失败: {error_msg}"
                ),
            )
            cleanup_cmd = ssh_cmd + [f"rm -f {remote_path}"]
            try:
                cleanup_process = await asyncio.create_subprocess_exec(
                    *cleanup_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await cleanup_process.wait()
            except Exception:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                pass
            raise RuntimeError(f"写入远程文件失败: {error_msg}")

        return remote_path

    async def _start_trojan_process(
        self, ssh_cmd: list[str], remote_trojan_path: str
    ) -> bool:
        """启动远程trojan进程。"""
        ssh_trojan_cmd = ssh_cmd + [f"/usr/bin/env python3 {remote_trojan_path}"]
        self.process = await asyncio.create_subprocess_exec(
            *ssh_trojan_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.stderr = self.process.stderr

        await asyncio.sleep(1)
        return True

    async def connect(self) -> bool:
        """连接到SSH服务器并启动trojan。

        假设ssh命令可以直接连接，不需要密码交互。

        Returns:
            连接是否成功
        """
        self.trojan_path = None
        self.remote_trojan_path = None
        self.process = None

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

        try:
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO", content=f"开始连接SSH服务器: {self.host}:{self.port}"
                ),
            )

            self.trojan_path = Path(tempfile.mktemp(suffix=".py"))
            trojan_file_path = Path(__file__).parent / "trojan.py"
            if not trojan_file_path.exists():
                raise FileNotFoundError(f"trojan.py文件不存在: {trojan_file_path}")
            trojan_content = trojan_file_path.read_text(encoding="utf-8")  # pylint: disable=unspecified-encoding
            self.trojan_path.write_text(trojan_content, encoding="utf-8")

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"检查远程机器Python版本: {self.host}:{self.port}",
                ),
            )

            if not await self._check_python_version(ssh_cmd):
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"远程机器Python版本检查失败: {self.host}:{self.port}",
                    ),
                )
                if self.trojan_path and self.trojan_path.exists():
                    self.trojan_path.unlink(missing_ok=True)
                return False

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO", content=f"Python版本检查通过: {self.host}:{self.port}"
                ),
            )

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"复制控制程序到远程机器: {self.host}:{self.port}",
                ),
            )

            remote_trojan_path = await self._copy_trojan_to_remote(ssh_cmd)
            self.remote_trojan_path = remote_trojan_path

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"控制程序已复制到远程机器: {self.host}:{self.port}",
                ),
            )

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO", content=f"启动远程控制程序: {self.host}:{self.port}"
                ),
            )

            if not await self._start_trojan_process(ssh_cmd, remote_trojan_path):
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"启动远程控制程序失败: {self.host}:{self.port}",
                    ),
                )
                await self._cleanup_remote_file(ssh_cmd, remote_trojan_path)
                if self.trojan_path and self.trojan_path.exists():
                    self.trojan_path.unlink(missing_ok=True)
                return False

            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"远程控制程序启动成功: {self.host}:{self.port}",
                ),
            )

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"SSH连接失败: {self.host}:{self.port}, 错误: {str(e)}",
                ),
            )
            await self._cleanup_on_connect_failure(ssh_cmd)
            return False

    async def _send_request(
        self, method: str, params: Dict[str, object]
    ) -> Dict[str, object]:
        """发送JSON RPC请求到trojan。"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request) + "\n"
        if self.stdin is None:
            raise ConnectionError("连接未建立，stdin为None")
        self.stdin.write(request_json.encode())
        await self.stdin.drain()

        if self.stdout is None:
            raise ConnectionError("连接未建立，stdout为None")
        response_line = await self.stdout.readline()
        if not response_line:
            raise ConnectionError("连接断开")

        response = json.loads(response_line.decode())

        if "error" in response:
            raise RuntimeError(f"RPC错误: {response['error']}")

        return response["result"]

    async def call_tool(
        self, name: str, args: Dict[str, object]
    ) -> ToolResultSuccess | ToolResultFailed:
        """调用指定工具。

        Args:
            name: 工具名称
            args: 工具参数

        Returns:
            工具执行结果
        """
        try:
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"在SSH机器 {self.host}:{self.port} 上执行命令: {name}",
                ),
            )

            result = await self._send_request(name, args)
            if "error" in result:
                return ToolResultFailed(content=f"工具执行失败: {result['error']}")
            return ToolResultSuccess(content=str(result["message"]))
        except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
            return ToolResultFailed(content=f"调用工具失败: {e}")

    async def close(self):
        """关闭连接。"""
        await self.group_chat.send(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"正在关闭SSH连接: {self.host}:{self.port}"
            ),
        )

        if self.process:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"终止进程时出错: {str(e)}"
                    ),
                )
            finally:
                try:
                    await self.process.wait()
                except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                    await self.group_chat.send(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING", content=f"等待进程结束时出错: {str(e)}"
                        ),
                    )

        await self.group_chat.send(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"远程进程已终止: {self.host}:{self.port}"
            ),
        )

        if self.trojan_path and self.trojan_path.exists():
            try:
                self.trojan_path.unlink()
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"删除本地临时文件时出错: {str(e)}"
                    ),
                )

        await self.group_chat.send(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"本地临时文件已清理: {self.host}:{self.port}"
            ),
        )

        if self.remote_trojan_path:
            try:
                ssh_cmd = [
                    "ssh",
                    f"{self.username}@{self.host}",
                    "-p",
                    str(self.port),
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ConnectTimeout=5",
                ]
                cleanup_cmd = ssh_cmd + [f"rm -f {self.remote_trojan_path}"]
                process = await asyncio.create_subprocess_exec(
                    *cleanup_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                        process.communicate(), timeout=10
                    )  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                    if process.returncode != 0:
                        error_msg = stderr.decode()
                        await self.group_chat.send(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"删除远程临时文件失败，返回码: {process.returncode}, 错误: {error_msg}",
                            ),
                        )
                        await self.group_chat.send(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"删除远程临时文件失败: {self.host}:{self.port}",
                            ),
                        )
                    else:
                        await self.group_chat.send(
                            "ui_log",
                            CliRuntimeNotice(
                                level="INFO",
                                content=f"远程临时文件已清理: {self.host}:{self.port}",
                            ),
                        )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                    await self.group_chat.send(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"删除远程临时文件超时: {self.host}:{self.port}",
                        ),
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                    await self.group_chat.send(
                        "ui_log",
                        CliRuntimeNotice(
                            level="ERROR",
                            content=f"删除远程临时文件时出错: {self.host}:{self.port}, 错误: {str(e)}",
                        ),
                    )
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"删除远程临时文件时出错: {self.host}:{self.port}, 错误: {str(e)}",
                    ),
                )

        await self.group_chat.send(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"SSH连接已完全关闭: {self.host}:{self.port}"
            ),
        )

    async def http_request(
        self,
        method: str,  # pylint: disable=unused-argument
        url: str,  # pylint: disable=unused-argument
        params: Optional[dict[str, Any]] = None,  # pylint: disable=unused-argument
        headers: Optional[dict[str, str]] = None,  # pylint: disable=unused-argument
        data: Optional[str] = None,  # pylint: disable=unused-argument
        follow_redirects: bool = True,  # pylint: disable=unused-argument
        timeout: int = 60,  # pylint: disable=unused-argument
    ) -> ToolResultSuccess | ToolResultFailed:
        """SSH不支持http_request工具"""
        return ToolResultFailed(content="SSH机器不支持http_request工具")

    async def run_command(
        self, command: str, timeout: float = 30.0
    ) -> ToolResultSuccess | ToolResultFailed:
        """执行系统命令"""
        return await self.call_tool(
            "run_command", {"command": command, "timeout": timeout}
        )

    async def change_directory(
        self, directory: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """改变当前工作目录"""
        return await self.call_tool("change_directory", {"directory": directory})

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> ToolResultSuccess | ToolResultFailed:
        """创建远程终端"""
        return await self.call_tool(
            "terminal_create", {"columns": columns, "lines": lines}
        )

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送按键到远程终端"""
        return await self.call_tool(
            "terminal_send_keys", {"term_id": terminal_id, "keys": keys}
        )

    async def terminal_send_string(
        self,
        terminal_id: str,
        string: str,
        with_enter: bool = True,
        wait_seconds: float = 0.3,  # pylint: disable=unused-argument
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送字符串到远程终端"""
        return await self.call_tool(
            "terminal_send_string",
            {"term_id": terminal_id, "string": string, "with_enter": with_enter},
        )

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取远程终端屏幕内容"""
        result = await self.call_tool("terminal_read_screen", {"term_id": terminal_id})
        if isinstance(result, ToolResultSuccess):
            # 解码base64
            import base64

            try:
                decoded_bytes = base64.b64decode(result.content)
                # 将字节流解码为字符串，使用utf-8并用替换字符替换无法解码的字节
                decoded_str = decoded_bytes.decode("utf-8", errors="replace")
                return ToolResultSuccess(content=decoded_str)
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                return ToolResultFailed(content=f"解码终端屏幕内容失败: {e}")
        return result

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """关闭远程终端"""
        return await self.call_tool("terminal_close", {"term_id": terminal_id})

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取文件"""
        return await self.call_tool(
            "read_file", {"filepath": filepath, "show_line_numbers": show_line_numbers}
        )

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> ToolResultSuccess | ToolResultFailed:
        """写入文件内容"""
        return await self.call_tool(
            "write_file",
            {"filepath": filepath, "content": content, "override": override},
        )

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> ToolResultSuccess | ToolResultFailed:
        """替换文件内容"""
        params: dict[str, str | int] = {"filepath": filepath, "old": old, "new": new}
        if replace_times is not None:
            params["replace_times"] = replace_times
        return await self.call_tool("replace_file_content", params)  # type: ignore

    async def list_files(self, dirpath: str) -> ToolResultSuccess | ToolResultFailed:
        """列出指定文件夹中的文件"""
        return await self.call_tool("list_files", {"dirpath": dirpath})

    async def get_absolute_path(
        self, path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """获取路径的绝对路径"""
        return await self.call_tool("get_absolute_path", {"path": path})

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """执行sed表达式并返回输出"""
        return await self.call_tool(
            "read_file_with_sed", {"expression": expression, "filepath": filepath}
        )

    async def modify_file_with_sed(
        self, expression: str, filepath: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """使用sed表达式修改文件"""
        return await self.call_tool(
            "modify_file_with_sed", {"expression": expression, "filepath": filepath}
        )

    async def insert_at_line(
        self,
        filepath: str,
        line_number: int,
        content: str,
        expected_line_content: str,
    ) -> ToolResultSuccess | ToolResultFailed:
        """将内容插入到文件的指定行号位置"""
        return await self.call_tool(
            "insert_at_line",
            {
                "filepath": filepath,
                "line_number": line_number,
                "content": content,
                "expected_line_content": expected_line_content,
            },
        )

    async def _cleanup_remote_file(self, ssh_cmd: list[str], remote_path: str) -> None:
        """清理远程临时文件。

        Args:
            ssh_cmd: SSH命令列表
            remote_path: 远程文件路径
        """
        try:
            cleanup_cmd = ssh_cmd + [f"rm -f {remote_path}"]
            process = await asyncio.create_subprocess_exec(
                *cleanup_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                    process.communicate(), timeout=10
                )  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                if process.returncode != 0:
                    error_msg = stderr.decode()
                    await self.group_chat.send(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"清理远程文件失败，返回码: {process.returncode}, 错误: {error_msg}",
                        ),
                    )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(level="WARNING", content="清理远程文件超时"),
                )
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR", content=f"清理远程文件时出错: {str(e)}"
                    ),
                )
        except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
            await self.group_chat.send(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR", content=f"清理远程文件时出错: {str(e)}"
                ),
            )

    async def _cleanup_on_connect_failure(self, ssh_cmd: list[str]) -> None:
        """连接失败时清理所有资源。

        Args:
            ssh_cmd: SSH命令列表
        """
        if self.remote_trojan_path:
            await self._cleanup_remote_file(ssh_cmd, self.remote_trojan_path)
        if self.trojan_path and self.trojan_path.exists():
            try:
                self.trojan_path.unlink(missing_ok=True)
            except Exception as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"删除本地临时文件时出错: {str(e)}"
                    ),
                )
