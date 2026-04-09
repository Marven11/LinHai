"""SSH机器控制类，用于通过SSH连接远程机器并执行工具。"""

import asyncio
import json
from typing import Dict, Optional, Any

from linhai.registry import Registry
from linhai.machine_control.http_message import HttpMessage, build_http_message
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils.common import UiNotice
from ..trojan.ssh_transport import SshTrojanTransport
from linhai.machine_control.process import (
    ProcessCreateResult,
    Process,
)
from .process import RemoteProcess


class SshMachineControl:
    """SSH机器控制类，负责通过SSH连接远程机器并调用工具。"""

    def __init__(
        self,
        host: str,
        registry: Registry,
        port: int = 22,
        username: Optional[str] = None,
    ):
        self.transport = SshTrojanTransport(host, registry, port, username)
        self.registry = registry
        self._username = username
        self._processes: dict[str, RemoteProcess] = {}

    @property
    def username(self) -> str | None:
        """返回SSH用户名"""
        return self._username

    async def connect(self) -> bool:
        """连接到SSH服务器并启动trojan。

        假设ssh命令可以直接连接，不需要密码交互。

        Returns:
            连接是否成功
        """
        try:
            return await self.transport.connect()
        except Exception as e:
            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="ERROR",
                    content=f"连接失败: {e}",
                ),
            )
            return False

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
            response = await self.transport.send_request(name, args)
        except ConnectionError as e:
            return ToolResultFailed(content=f"连接已失效: {e}")
        except Exception as e:
            return ToolResultFailed(content=f"请求失败: {e}")

        if "error" in response:
            error_content = response["error"]
            if isinstance(error_content, dict) and "message" in error_content:
                error_message = error_content["message"]
            else:
                error_message = str(error_content)
            return ToolResultFailed(content=f"工具执行失败: {error_message}")

        result = response.get("result")
        if result is None:
            return ToolResultFailed(content="响应中缺少result字段")

        if isinstance(result, dict) and "message" in result:
            return ToolResultSuccess(content=str(result["message"]))
        else:
            return ToolResultSuccess(content=str(result))

    async def close(self):
        """关闭连接。"""
        await self.transport.disconnect()

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpMessage | ToolResultFailed:
        import base64 as _base64

        args: Dict[str, Any] = {
            "method": method,
            "url": url,
            "follow_redirects": follow_redirects,
            "timeout": timeout,
        }
        if params is not None:
            args["params"] = params
        if headers is not None:
            args["headers"] = headers
        if data is not None:
            args["data"] = data
        if auth is not None:
            args["auth"] = list(auth)
        if cookies is not None:
            args["cookies"] = cookies
        if json_data is not None:
            args["json_data"] = json_data
        if proxy is not None:
            args["proxy"] = proxy
        if verify is not None:
            args["verify"] = verify

        result = await self.call_tool("http_request", args)
        if isinstance(result, ToolResultFailed):
            return result

        resp_data = json.loads(result.content)
        content_bytes = _base64.b64decode(resp_data["content_base64"])

        return await build_http_message(
            status_code=resp_data["status_code"],
            headers=resp_data["headers"],
            content=content_bytes,
            content_type=resp_data.get("content_type", ""),
        )

    async def create_process(
        self, argv: list[str], wait_second: Optional[float] = None
    ) -> ProcessCreateResult:
        """创建一个进程并返回进程对象"""
        from linhai.machine_control.http_message import HttpMessage

        if wait_second is None:
            wait_second = 1.0

        result = await self.call_tool(
            "process_create", {"argv": argv, "wait_second": wait_second}
        )

        if isinstance(result, ToolResultFailed):
            return ProcessCreateResult(
                process=None,
                pid="",
                error=result.content,
            )

        data = json.loads(result.content)
        pid = str(data.get("pid", ""))
        returncode = data.get("returncode")
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
        message = data.get("message", "")

        def on_exit(p: str) -> None:
            if p in self._processes:
                del self._processes[p]

        process = RemoteProcess(
            pid=pid,
            call_tool=self.call_tool,
            on_exit=on_exit,
        )
        self._processes[pid] = process

        return ProcessCreateResult(
            process=process,
            pid=pid,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            message=message,
        )

    def get_process(self, pid: str) -> Process | None:
        """获取已有进程对象"""
        return self._processes.get(pid)

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
        wait_seconds: float = 0.3,
    ) -> ToolResultSuccess | ToolResultFailed:
        """发送字符串到远程终端"""
        return await self.call_tool(
            "terminal_send_string",
            {
                "term_id": terminal_id,
                "string": string,
                "with_enter": with_enter,
                "wait_seconds": wait_seconds,
            },
        )

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> ToolResultSuccess | ToolResultFailed:
        """读取远程终端屏幕内容"""
        result = await self.call_tool("terminal_read_screen", {"term_id": terminal_id})
        if isinstance(result, ToolResultSuccess):
            import base64

            decoded_bytes = base64.b64decode(result.content)
            decoded_str = decoded_bytes.decode("utf-8", errors="replace")
            return ToolResultSuccess(content=decoded_str)
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
        params: Dict[str, Any] = {"filepath": filepath, "old": old, "new": new}
        if replace_times is not None:
            params["replace_times"] = replace_times
        return await self.call_tool("replace_file_content", params)

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
        import base64
        import math

        chunk_size = 32 * 1024
        num_chunks = math.ceil(len(data) / chunk_size)

        temp_dir_result = await self.call_tool("create_temp_dir", {"prefix": "upload_"})
        if isinstance(temp_dir_result, ToolResultFailed):
            return ToolResultFailed(
                content=f"创建临时目录失败: {temp_dir_result.content}"
            )
        temp_dir = temp_dir_result.content

        max_concurrent = 16
        semaphore = asyncio.Semaphore(max_concurrent)

        async def upload_chunk(chunk_index: int, chunk_data: bytes) -> tuple[int, str]:
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
                if isinstance(result, ToolResultFailed):
                    raise RuntimeError(f"上传块失败: {result.content}")
                return (chunk_index, chunk_path)

        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )

        chunk_results: dict[int, str] = {}

        for i in range(num_chunks):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, len(data))
            chunk_data = data[start:end]

            async def _upload_wrapper(idx: int = i, cd: bytes = chunk_data) -> None:
                result = await upload_chunk(idx, cd)
                chunk_results[idx] = result[1]

            task_supervisor.create_supervised_task(f"upload_chunk_{i}", _upload_wrapper)

        for i in range(num_chunks):
            await task_supervisor.wait(f"upload_chunk_{i}")

        chunk_paths = [(i, chunk_results[i]) for i in range(num_chunks)]

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
        import base64
        import math

        size_result = await self.call_tool("get_file_size", {"filepath": remote_path})
        if isinstance(size_result, ToolResultFailed):
            return ToolResultFailed(content=f"获取文件大小失败: {size_result.content}")

        file_size = int(size_result.content)

        chunk_size = 32 * 1024
        num_chunks = math.ceil(file_size / chunk_size)

        max_concurrent = 16
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_chunk(chunk_index: int) -> bytes:
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
                if isinstance(result, ToolResultFailed):
                    raise RuntimeError(f"下载块失败: {result.content}")
                chunk_data = base64.b64decode(result.content)
                if len(chunk_data) != length:
                    raise RuntimeError(
                        f"下载块大小不匹配: 预期{length}, 实际{len(chunk_data)}"
                    )
                return chunk_data

        from linhai.task_supervisor import TaskSupervisor

        task_supervisor = self.registry.get_member_typechecked(
            "task_supervisor", TaskSupervisor
        )

        chunk_results: dict[int, bytes] = {}

        for i in range(num_chunks):

            async def _download_wrapper(idx: int = i) -> None:
                result = await download_chunk(idx)
                chunk_results[idx] = result

            task_supervisor.create_supervised_task(
                f"download_chunk_{i}", _download_wrapper
            )

        for i in range(num_chunks):
            await task_supervisor.wait(f"download_chunk_{i}")

        chunks = [chunk_results[i] for i in range(num_chunks)]

        with open(local_path, "wb") as f:
            for chunk_data in chunks:
                f.write(chunk_data)

        return ToolResultSuccess(content=f"文件已下载: {local_path}")
