import asyncio
import json
from typing import Dict, Optional, Any

from linhai.registry import Registry
from linhai.machine_control.http_message import HttpMessage, build_http_message
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from ..trojan.transport import TrojanTransport
from ..trojan.shell_transport import setup_trojan_in_shell
from .process import RemoteProcess
from ..process import Process, ProcessCreateResult


class PosixShellControl:
    def __init__(
        self,
        registry: Registry,
        host: str = "",
        port: int = 22,
    ):
        self.registry = registry
        self._machine_id: str = ""
        self._host = host
        self._port = port
        self.registry = registry
        self._processes: dict[str, RemoteProcess] = {}
        self.transport: Optional[TrojanTransport] = None

    async def connect(self, process: Process) -> bool:
        result = await setup_trojan_in_shell(process, self.registry)
        if result is None:
            return False
        remote_path, marker_hex = result

        self.transport = TrojanTransport(
            registry=self.registry, process=process, marker_hex=marker_hex
        )
        self.transport.start_reading()
        return True

    async def call_tool(
        self, name: str, args: Dict[str, object]
    ) -> SuccessfulToolResult | FailedToolResult:
        if self.transport is None:
            return FailedToolResult(content="未建立连接")

        response = await self.transport.send_request(name, args)
        result = response.get("result")
        if isinstance(result, dict) and "message" in result:
            return SuccessfulToolResult(content=str(result["message"]))
        else:
            return SuccessfulToolResult(content=str(result))

    async def ping(self) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool("ping", {})

    async def disconnect(self) -> None:
        if self.transport:
            await self.transport.disconnect()
            self.transport = None

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
    ) -> HttpMessage | FailedToolResult:
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
        if isinstance(result, FailedToolResult):
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
        self,
        argv: list[str],
        wait_second: Optional[float] = None,
        pty: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> ProcessCreateResult:
        if pty:
            raise RuntimeError("PosixShell不支持pty模式")
        if wait_second is None:
            wait_second = 1.0
        args: Dict[str, object] = {"argv": argv, "wait_second": wait_second}
        if env is not None:
            args["env"] = env
        result = await self.call_tool("process_create", args)
        if isinstance(result, FailedToolResult):
            return ProcessCreateResult(pid="", success=False, error=result.content)

        data = json.loads(result.content)
        pid = data.get("pid")
        if pid is None:
            return ProcessCreateResult(pid="", success=False, error="无法解析进程ID")

        if "returncode" in data:
            return ProcessCreateResult(
                pid=pid,
                success=True,
                returncode=data["returncode"],
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
            )

        rp = RemoteProcess(pid, self)
        self._processes[pid] = rp
        return ProcessCreateResult(
            pid=pid, success=True, returncode=None, message=data.get("message", "")
        )

    def get_process(self, pid: str) -> Process | None:
        return self._processes.get(pid)

    def list_process_pids(self) -> list[str]:
        return list(self._processes.keys())

    async def change_directory(
        self, directory: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool("change_directory", {"directory": directory})

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool(
            "terminal_create", {"columns": columns, "lines": lines}
        )

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool(
            "terminal_send_keys", {"term_id": terminal_id, "keys": keys}
        )

    async def terminal_send_string(
        self,
        terminal_id: str,
        string: str,
        with_enter: bool = True,
        wait_seconds: float = 0.3,
    ) -> SuccessfulToolResult | FailedToolResult:
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
    ) -> SuccessfulToolResult | FailedToolResult:
        result = await self.call_tool("terminal_read_screen", {"term_id": terminal_id})
        if isinstance(result, SuccessfulToolResult):
            import base64

            decoded_bytes = base64.b64decode(result.content)
            decoded_str = decoded_bytes.decode("utf-8", errors="replace")
            return SuccessfulToolResult(content=decoded_str)
        return result

    async def terminal_close(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool("terminal_close", {"term_id": terminal_id})

    async def get_terminals(self) -> SuccessfulToolResult | FailedToolResult:
        result = await self.call_tool("terminal_list", {})
        if isinstance(result, SuccessfulToolResult):
            return SuccessfulToolResult(content=result.content)
        else:
            return FailedToolResult(
                content=f"获取终端列表失败: {result.content}",
            )

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool(
            "read_file", {"filepath": filepath, "show_line_numbers": show_line_numbers}
        )

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool(
            "write_file",
            {"filepath": filepath, "content": content, "override": override},
        )

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult:
        params: Dict[str, Any] = {"filepath": filepath, "old": old, "new": new}
        if replace_times is not None:
            params["replace_times"] = replace_times
        return await self.call_tool("replace_file_content", params)

    async def list_files(self, dirpath: str) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool("list_files", {"dirpath": dirpath})

    async def list_files_glob(
        self, pattern: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return FailedToolResult(content="list_files_glob仅支持master_host")

    async def get_absolute_path(
        self, path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool("get_absolute_path", {"path": path})

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult:
        return await self.call_tool(
            "read_file_with_sed", {"expression": expression, "filepath": filepath}
        )

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        import base64
        import math

        chunk_size = 32 * 1024
        num_chunks = math.ceil(len(data) / chunk_size)

        temp_dir_result = await self.call_tool("create_temp_dir", {"prefix": "upload_"})
        if isinstance(temp_dir_result, FailedToolResult):
            return FailedToolResult(
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
                if isinstance(result, FailedToolResult):
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
        if isinstance(concat_result, FailedToolResult):
            await self.call_tool("remove_path", {"path": temp_dir})
            return concat_result

        await self.call_tool("remove_path", {"path": temp_dir})
        return SuccessfulToolResult(content=f"文件已上传: {remote_path}")

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> SuccessfulToolResult | FailedToolResult:
        import base64
        import math

        size_result = await self.call_tool("get_file_size", {"filepath": remote_path})
        if isinstance(size_result, FailedToolResult):
            return FailedToolResult(content=f"获取文件大小失败: {size_result.content}")

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
                if isinstance(result, FailedToolResult):
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

        return SuccessfulToolResult(content=f"文件已下载: {local_path}")
