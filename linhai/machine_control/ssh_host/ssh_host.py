"""SSH机器控制类，用于通过SSH连接远程机器并执行工具。"""

from typing import Dict, Optional, Any, cast
import asyncio
import json
import tempfile
import uuid
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
        self.results: Dict[str, object] = {}
        self.reader_task: Optional[asyncio.Task] = None

    async def _check_python_version(self, ssh_cmd: list[str]) -> bool:
        """检查远程机器上的Python版本。"""
        check_cmd = ssh_cmd + ["/usr/bin/env python3 -V"]
        process = await asyncio.create_subprocess_exec(
            *check_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = (
            await process.communicate()
        )  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
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
        """将trojan.py复制到远程机器，返回远程临时文件路径。"""
        if self.trojan_path is None or not self.trojan_path.exists():
            raise FileNotFoundError("本地trojan临时文件不存在")

        trojan_content = self.trojan_path.read_text(
            encoding="utf-8"
        )  # pylint: disable=unspecified-encoding

        remote_temp_path_cmd = ssh_cmd + ["mktemp --suffix=.py"]
        process = await asyncio.create_subprocess_exec(
            *remote_temp_path_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = (
            await process.communicate()
        )  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
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

        import base64

        encoded_content = base64.b64encode(trojan_content.encode()).decode()
        echo_cmd = ssh_cmd + [f"echo {encoded_content} | base64 -d > {remote_path}"]
        process = await asyncio.create_subprocess_exec(
            *echo_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = (
            await process.communicate()
        )  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
        if process.returncode != 0:
            error_msg = stderr.decode()
            await self.group_chat.send_if_exists(
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
            except (
                Exception
            ):  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
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
            trojan_content = trojan_file_path.read_text(
                encoding="utf-8"
            )  # pylint: disable=unspecified-encoding
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

            if not await self._start_trojan_process(ssh_cmd, remote_trojan_path):
                await self.group_chat.send_if_exists(
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

            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="INFO",
                    content=f"远程控制程序启动成功: {self.host}:{self.port}",
                ),
            )

            self.reader_task = asyncio.create_task(self._read_responses())

            return True

        except (
            Exception
        ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
            await self.group_chat.send_if_exists(
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
        request_id = uuid.uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request) + "\n"
        if self.stdin is None:
            raise ConnectionError("连接未建立，stdin为None")
        self.stdin.write(request_json.encode())
        await self.stdin.drain()

        self.results[request_id] = None
        try:

            async def wait_for_response() -> Dict[str, object]:
                while self.results[request_id] is None:
                    await asyncio.sleep(0.01)
                result = self.results.pop(request_id)
                if result is None:
                    raise ConnectionError("未收到响应")
                return cast(Dict[str, object], result)

            return await asyncio.wait_for(wait_for_response(), timeout=60.0)
        except asyncio.TimeoutError:
            self.results.pop(request_id, None)
            raise ConnectionError("请求超时（60秒）")
        except Exception as e:
            self.results.pop(request_id, None)
            raise e

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
        response = await self._send_request(name, args)  # 现在response是整个响应
        if "error" in response:
            # 错误响应
            error_content = response["error"]
            if isinstance(error_content, dict) and "message" in error_content:
                error_message = error_content["message"]
            else:
                error_message = str(error_content)
            return ToolResultFailed(content=f"工具执行失败: {error_message}")
        result = response.get("result")
        if result is None:
            return ToolResultFailed(content="响应中缺少result字段")
        if "message" in result:
            return ToolResultSuccess(content=str(result["message"]))
        else:
            return ToolResultSuccess(content=str(result))

    async def _read_responses(self) -> None:
        while True:
            if self.stdout is None:
                await asyncio.sleep(0.1)
                continue
            try:
                line = await self.stdout.readline()
                if not line:
                    break
                response = json.loads(line.decode())
                response_id = response.get("id")
                if response_id is not None:
                    self.results[response_id] = response  # 存储整个响应
            except Exception as e:
                # 记录异常但继续循环，避免因单个响应解析失败而终止
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"读取响应时出错: {e}",
                    ),
                )
                continue

    async def close(self):
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        await self.group_chat.send_if_exists(
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
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"终止进程时出错: {str(e)}"
                    ),
                )
            finally:
                try:
                    await self.process.wait()
                except (
                    Exception
                ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING", content=f"等待进程结束时出错: {str(e)}"
                        ),
                    )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"远程进程已终止: {self.host}:{self.port}"
            ),
        )

        if self.trojan_path and self.trojan_path.exists():
            try:
                self.trojan_path.unlink()
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"删除本地临时文件时出错: {str(e)}"
                    ),
                )

        await self.group_chat.send_if_exists(
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
                    stdout, stderr = (
                        await asyncio.wait_for(  # pylint: disable=unused-variable  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                            process.communicate(), timeout=10
                        )
                    )  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                    if process.returncode != 0:
                        error_msg = stderr.decode()
                        await self.group_chat.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"删除远程临时文件失败，返回码: {process.returncode}, 错误: {error_msg}",
                            ),
                        )
                        await self.group_chat.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="WARNING",
                                content=f"删除远程临时文件失败: {self.host}:{self.port}",
                            ),
                        )
                    else:
                        await self.group_chat.send_if_exists(
                            "ui_log",
                            CliRuntimeNotice(
                                level="INFO",
                                content=f"远程临时文件已清理: {self.host}:{self.port}",
                            ),
                        )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"删除远程临时文件超时: {self.host}:{self.port}",
                        ),
                    )
                except (
                    Exception
                ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="ERROR",
                            content=f"删除远程临时文件时出错: {self.host}:{self.port}, 错误: {str(e)}",
                        ),
                    )
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"删除远程临时文件时出错: {self.host}:{self.port}, 错误: {str(e)}",
                    ),
                )

        await self.group_chat.send_if_exists(
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

    async def process_create(
        self, command: list[str], wait_second: float = 1.0
    ) -> ToolResultSuccess | ToolResultFailed:
        """创建一个进程，等待一段时间后检查状态"""
        return await self.call_tool(
            "process_create", {"command": command, "wait_second": wait_second}
        )

    async def process_stdio_write(
        self, pid: str, content: str, with_enter: bool
    ) -> ToolResultSuccess | ToolResultFailed:
        """向进程的标准输入写入内容"""
        return await self.call_tool(
            "process_stdio_write", {"pid": pid, "content": content, "with_enter": with_enter}
        )

    async def process_stdio_read(
        self, pid: str, unescape_ansi: bool = True, timeout: float = 60.0
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取进程的标准输出和标准错误内容"""
        return await self.call_tool(
            "process_stdio_read", {"pid": pid, "unescape_ansi": unescape_ansi, "timeout": timeout}
        )

    async def process_wait(
        self, pid: str, timeout: float
    ) -> ToolResultSuccess | ToolResultFailed:
        """等待进程结束，带超时设置"""
        return await self.call_tool("process_wait", {"pid": pid, "timeout": timeout})

    async def process_kill(
        self, pid: str, graceful: bool = True
    ) -> ToolResultSuccess | ToolResultFailed:
        """杀死进程，可选择优雅终止"""
        return await self.call_tool("process_kill", {"pid": pid, "graceful": graceful})

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
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                return ToolResultFailed(content=f"解码终端屏幕内容失败: {e}")
        return result

    async def terminal_close(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """关闭远程终端"""
        return await self.call_tool("terminal_close", {"term_id": terminal_id})

    async def get_terminals(self) -> ToolResultSuccess | ToolResultFailed:
        """获取远程终端列表"""
        result = await self.call_tool("terminal_list", {})
        if isinstance(result, ToolResultSuccess):
            return ToolResultSuccess(content=result.content)
        else:
            return ToolResultFailed(
                content=f"获取终端列表失败: {result.content}",
            )

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

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """并发上传文件到远程机器。

        Args:
            data: 文件内容（bytes）
            remote_path: 远程文件路径

        Returns:
            执行结果
        """
        try:
            import base64
            import math

            chunk_size = 32 * 1024
            num_chunks = math.ceil(len(data) / chunk_size)

            temp_dir_result = await self.call_tool(
                "create_temp_dir", {"prefix": "upload_"}
            )
            if isinstance(temp_dir_result, ToolResultFailed):
                return ToolResultFailed(
                    content=f"创建临时目录失败: {temp_dir_result.content}"
                )
            temp_dir = temp_dir_result.content

            max_concurrent = 16
            max_retries = 3
            done_chunks = 0
            semaphore = asyncio.Semaphore(max_concurrent)

            async def upload_chunk_with_retry(
                chunk_index: int, chunk_data: bytes
            ) -> tuple[int, str]:
                nonlocal done_chunks
                for attempt in range(max_retries):
                    try:
                        async with semaphore:
                            chunk_base64 = base64.b64encode(chunk_data).decode("utf-8")
                            chunk_filename = f"chunk_{chunk_index:010d}"
                            chunk_path = f"{temp_dir}/{chunk_filename}"
                            result = await self.call_tool(
                                "upload_chunk",
                                {
                                    "chunk_data_base64": chunk_base64,
                                    "filepath": chunk_path,
                                },
                            )
                            if isinstance(result, ToolResultSuccess):
                                done_chunks += 1
                                if done_chunks % 50 == 10:
                                    await self.group_chat.send_if_exists(
                                        "ui_log",
                                        CliRuntimeNotice(
                                            level="INFO",
                                            content=f"上传文件已完成: {done_chunks}/{num_chunks}",
                                        ),
                                    )
                                return (chunk_index, chunk_path)
                            else:
                                if attempt == max_retries - 1:
                                    raise RuntimeError(f"上传块失败: {result.content}")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(1.0 * (attempt + 1))
                raise RuntimeError("所有重试都失败")

            chunk_paths = []
            tasks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = min((i + 1) * chunk_size, len(data))
                chunk_data = data[start:end]
                task = asyncio.create_task(upload_chunk_with_retry(i, chunk_data))
                tasks.append(task)
                await asyncio.sleep(0)

            for i, task in enumerate(tasks):
                try:
                    chunk_index, chunk_path = await task
                    chunk_paths.append((chunk_index, chunk_path))
                except Exception as e:
                    for t in tasks[i + 1 :]:
                        t.cancel()
                    await asyncio.gather(*tasks[i + 1 :], return_exceptions=True)
                    await self.call_tool("remove_path", {"path": temp_dir})
                    return ToolResultFailed(content=f"上传块失败: {e}")

            chunk_paths.sort(key=lambda x: x[0])
            chunk_paths_sorted = [path for _, path in chunk_paths]
            concat_result = await self.call_tool(
                "concatenate_files",
                {"filepaths": chunk_paths_sorted, "output_path": remote_path},
            )
            if isinstance(concat_result, ToolResultFailed):
                await self.call_tool("remove_path", {"path": temp_dir})
                return concat_result

            await self.call_tool("remove_path", {"path": temp_dir})
            return ToolResultSuccess(content=f"文件已上传: {remote_path}")

        except Exception as e:
            return ToolResultFailed(content=f"并发上传文件失败: {e}")

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """从远程机器并发下载文件到本地。

        Args:
            remote_path: 远程文件路径
            local_path: 本地保存路径

        Returns:
            执行结果
        """
        try:
            import base64
            import math

            size_result = await self.call_tool(
                "get_file_size", {"filepath": remote_path}
            )
            if isinstance(size_result, ToolResultFailed):
                return ToolResultFailed(
                    content=f"获取文件大小失败: {size_result.content}"
                )

            try:
                file_size = int(size_result.content)
            except ValueError:
                return ToolResultFailed(
                    content=f"无效的文件大小: {size_result.content}"
                )

            chunk_size = 32 * 1024
            num_chunks = math.ceil(file_size / chunk_size)

            max_concurrent = 16
            max_retries = 3
            semaphore = asyncio.Semaphore(max_concurrent)

            async def download_chunk_with_retry(chunk_index: int) -> bytes:
                for attempt in range(max_retries):
                    try:
                        async with semaphore:
                            offset = chunk_index * chunk_size
                            length = min(chunk_size, file_size - offset)
                            result = await self.call_tool(
                                "download_chunk",
                                {
                                    "filepath": remote_path,
                                    "offset": offset,
                                    "length": length,
                                },
                            )
                            if isinstance(result, ToolResultSuccess):
                                chunk_data = base64.b64decode(result.content)
                                if len(chunk_data) != length:
                                    raise RuntimeError(
                                        f"下载块大小不匹配: 预期{length}, 实际{len(chunk_data)}"
                                    )
                                return chunk_data
                            else:
                                if attempt == max_retries - 1:
                                    raise RuntimeError(f"下载块失败: {result.content}")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(1.0 * (attempt + 1))
                raise RuntimeError("所有重试都失败")

            chunks = [None] * num_chunks
            tasks = []
            for i in range(num_chunks):
                task = asyncio.create_task(download_chunk_with_retry(i))
                tasks.append(task)

            for i, task in enumerate(tasks):
                try:
                    chunk_data = await task
                    chunks[i] = chunk_data
                except Exception as e:
                    for t in tasks[i + 1 :]:
                        t.cancel()
                    await asyncio.gather(*tasks[i + 1 :], return_exceptions=True)
                    return ToolResultFailed(content=f"下载块失败: {e}")

            with open(local_path, "wb") as f:
                for chunk_data in chunks:
                    if chunk_data is None:
                        return ToolResultFailed(content="块数据为None")
                    f.write(chunk_data)

            return ToolResultSuccess(content=f"文件已下载: {local_path}")

        except Exception as e:
            return ToolResultFailed(content=f"并发下载文件失败: {e}")

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
                stdout, stderr = (
                    await asyncio.wait_for(  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                        process.communicate(), timeout=10
                    )
                )  # pylint: disable=unused-variable  # pylint: disable=unused-variable
                if process.returncode != 0:
                    error_msg = stderr.decode()
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="WARNING",
                            content=f"清理远程文件失败，返回码: {process.returncode}, 错误: {error_msg}",
                        ),
                    )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(level="WARNING", content="清理远程文件超时"),
                )
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR", content=f"清理远程文件时出错: {str(e)}"
                    ),
                )
        except (
            Exception
        ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
            await self.group_chat.send_if_exists(
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
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught  # pylint: disable=broad-exception-caught
                await self.group_chat.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="WARNING", content=f"删除本地临时文件时出错: {str(e)}"
                    ),
                )
