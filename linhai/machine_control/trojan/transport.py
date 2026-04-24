import asyncio
import json
import uuid
from typing import Dict, Any, Optional

from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.machine_control.process import Process


class JsonRpcResponse(Dict[str, Any]):
    pass


class TrojanTransport:
    def __init__(
        self,
        registry: Registry,
        process: Process,
        marker_hex: str,
    ):
        self.registry = registry
        self._process: Process = process
        self._marker_open = f"<linhai_trojanpy_{marker_hex}>"
        self._marker_close = f"</linhai_trojanpy_{marker_hex}>"
        self._buffer = b""
        self._pending_futures: Dict[str, asyncio.Future[JsonRpcResponse]] = {}
        self._reader_started: bool = False
        self._connection_valid = True

    async def _read_marker_data(self, timeout: float = 1.0) -> Optional[str]:
        open_bytes = self._marker_open.encode()
        close_bytes = self._marker_close.encode()
        while True:
            start_idx = self._buffer.find(open_bytes)
            if start_idx != -1:
                close_idx = self._buffer.find(close_bytes, start_idx)
                if close_idx != -1:
                    json_start = start_idx + len(open_bytes)
                    json_bytes = self._buffer[json_start:close_idx]
                    self._buffer = self._buffer[close_idx + len(close_bytes) :]
                    return json_bytes.decode("utf-8", errors="replace")
            result = await self._process.stdio_read(timeout)
            if not result.success or (
                not result.stdout and result.exit_note is not None
            ):
                return None
            if not result.stdout:
                continue
            self._buffer += result.stdout

    def start_reading(self) -> None:
        if not self._reader_started:
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            task_supervisor.create_supervised_task(
                "trojan_transport_reader", self._read_responses
            )
            self._reader_started = True

    async def _send_request(
        self, method: str, params: Dict[str, Any]
    ) -> JsonRpcResponse:
        if not self._connection_valid:
            raise ConnectionError("连接已失效")

        request_id = uuid.uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request)
        wrapped = f"{self._marker_open}{request_json}{self._marker_close}"
        write_result = await self._process.stdio_write(wrapped, with_enter=False)
        if not write_result.success:
            raise ConnectionError(f"写入失败: {write_result.error}")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[JsonRpcResponse] = loop.create_future()
        self._pending_futures[request_id] = future

        done, _ = await asyncio.wait({future}, timeout=60.0)
        self._pending_futures.pop(request_id, None)
        if not done:
            raise ConnectionError("请求超时")
        return next(iter(done)).result()

    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        results = await asyncio.gather(
            self._send_request(method, params), return_exceptions=True
        )
        result = results[0]
        if isinstance(result, ConnectionError):
            self._connection_valid = False
            raise result
        if isinstance(result, BaseException):
            raise result
        response = dict(result)
        if "error" in response:
            error_content = response["error"]
            if isinstance(error_content, dict) and "message" in error_content:
                raise RuntimeError(error_content["message"])
            raise RuntimeError(str(error_content))
        resp_result = response.get("result")
        if resp_result is None:
            raise RuntimeError("响应中缺少result字段")
        return response

    async def _read_one_response(self) -> None:
        data = await self._read_marker_data(timeout=1.0)
        if data is None:
            self._connection_valid = False
            self._fail_pending_futures()
            return
        response = json.loads(data)
        response_id = response.get("id")
        if response_id is not None:
            future = self._pending_futures.pop(response_id, None)
            if future is not None and not future.done():
                future.set_result(response)

    async def _read_responses(self) -> None:
        while self._connection_valid:
            results = await asyncio.gather(
                self._read_one_response(), return_exceptions=True
            )
            result = results[0]
            if isinstance(result, BaseException):
                if not isinstance(result, asyncio.CancelledError):
                    await self.registry.send_if_exists(
                        "ui_log",
                        UiNotice(
                            level="ERROR",
                            content=f"读取响应时出错: {result}",
                        ),
                    )
                    self._connection_valid = False
                    self._fail_pending_futures()
                break

    def _fail_pending_futures(self) -> None:
        for future in self._pending_futures.values():
            if not future.done():
                future.set_exception(ConnectionError("连接已失效"))
        self._pending_futures.clear()

    async def disconnect(self):
        if self._reader_started:
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            task_supervisor.cancel("trojan_transport_reader")
            await asyncio.gather(
                task_supervisor.wait("trojan_transport_reader"),
                return_exceptions=True,
            )

        if self._process:
            await self._process.kill(graceful=True)

        self._connection_valid = False
        self._fail_pending_futures()

    def is_connected(self) -> bool:
        return self._connection_valid

    async def wait_for_disconnect(self):
        if self._reader_started:
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            await task_supervisor.wait("trojan_transport_reader")
