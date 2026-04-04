import asyncio
import json
import uuid
from asyncio.subprocess import Process
from typing import Dict, Any, Optional

from linhai.registry import Registry
from linhai.utils.common import UiNotice


class JsonRpcResponse(Dict[str, Any]):
    pass


class TrojanTransport:
    def __init__(
        self,
        registry: Registry,
        stdin: Optional[asyncio.StreamWriter] = None,
        stdout: Optional[asyncio.StreamReader] = None,
        stderr: Optional[asyncio.StreamReader] = None,
        process: Optional[Process] = None,
    ):
        self.registry = registry
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.process = process
        self._pending_futures: Dict[str, asyncio.Future[JsonRpcResponse]] = {}
        self._reader_started: bool = False
        self._connection_valid = True

    def set_stdio(
        self,
        stdin: asyncio.StreamWriter,
        stdout: asyncio.StreamReader,
        stderr: asyncio.StreamReader,
        process: Process,
    ) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.process = process
        self._connection_valid = True

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

        if self.stdin is None:
            raise ConnectionError("连接未建立，stdin为None")

        request_id = uuid.uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request) + "\n"
        self.stdin.write(request_json.encode())
        await self.stdin.drain()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[JsonRpcResponse] = loop.create_future()
        self._pending_futures[request_id] = future

        done, _ = await asyncio.wait({future}, timeout=60.0)
        self._pending_futures.pop(request_id, None)
        if not done:
            raise ConnectionError("请求超时")
        return next(iter(done)).result()

    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self._send_request(method, params)
            return dict(response)
        except ConnectionError as e:
            self._connection_valid = False
            raise

    async def _read_responses(self) -> None:
        while True:
            if not self._connection_valid:
                break
            if self.stdout is None:
                await asyncio.sleep(0.1)
                continue
            try:
                line = await self.stdout.readline()
                if not line:
                    self._connection_valid = False
                    self._fail_pending_futures()
                    break
                response = json.loads(line.decode())
                response_id = response.get("id")
                if response_id is not None:
                    future = self._pending_futures.pop(response_id, None)
                    if future is not None and not future.done():
                        future.set_result(response)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.registry.send_if_exists(
                    "ui_log",
                    UiNotice(
                        level="ERROR",
                        content=f"读取响应时出错: {e}",
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
            try:
                await task_supervisor.wait("trojan_transport_reader")
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=60.0)

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
