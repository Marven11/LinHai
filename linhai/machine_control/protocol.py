from typing import Dict, Optional, Protocol, Union, Any
from linhai.machine_control.http_message import HttpMessage
from linhai.agent.messages import FileContentMessage
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from .process import Process, ProcessCreateResult


class HostControl(Protocol):
    """主机控制协议，所有机器控制类必须实现此接口。"""

    async def http_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpMessage | FailedToolResult: ...

    async def change_directory(
        self, directory: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def create_process(
        self,
        argv: list[str],
        wait_second: Optional[float] = None,
        pty: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> ProcessCreateResult: ...

    def get_process(self, pid: str) -> Process | None: ...

    async def terminal_create(
        self, columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def terminal_send_keys(
        self, terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def terminal_send_string(
        self, terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def terminal_read_screen(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def terminal_close(
        self, terminal_id: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def read_file(
        self, filepath: str, show_line_numbers: bool = False
    ) -> Union[SuccessfulToolResult, FailedToolResult, FileContentMessage]: ...

    async def write_file(
        self, filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def replace_file_content(
        self, filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def list_files(
        self, dirpath: str, glob: bool = False
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def get_absolute_path(
        self, path: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def read_file_with_sed(
        self, expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def get_terminals(self) -> SuccessfulToolResult | FailedToolResult: ...

    def list_process_pids(self) -> list[str]: ...

    async def ping(self) -> SuccessfulToolResult | FailedToolResult: ...

    async def download_file_concurrent(
        self, remote_path: str, local_path: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def upload_file_concurrent(
        self, data: bytes, remote_path: str
    ) -> SuccessfulToolResult | FailedToolResult: ...

    async def disconnect(self) -> None: ...
