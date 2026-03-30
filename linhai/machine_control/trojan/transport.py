import asyncio
import json
import uuid
from asyncio.subprocess import Process
from typing import Dict, Any, Optional

from linhai.registry import Registry
from linhai.utils import CliRuntimeNotice


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
        self.results: Dict[str, Optional[JsonRpcResponse]] = {}
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

        self.results[request_id] = None

        async def wait_for_response() -> JsonRpcResponse:
            while self.results[request_id] is None:
                if not self._connection_valid:
                    raise ConnectionError("连接已失效")
                await asyncio.sleep(0.01)
            result = self.results.pop(request_id)
            if result is None:
                raise ConnectionError("未收到响应")
            return result

        return await asyncio.wait_for(wait_for_response(), timeout=60.0)

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
                    break
                response = json.loads(line.decode())
                response_id = response.get("id")
                if response_id is not None:
                    self.results[response_id] = response
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.registry.send_if_exists(
                    "ui_log",
                    CliRuntimeNotice(
                        level="ERROR",
                        content=f"读取响应时出错: {e}",
                    ),
                )
                self._connection_valid = False
                break

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

    def is_connected(self) -> bool:
        return self._connection_valid

    async def wait_for_disconnect(self):
        if self._reader_started:
            from linhai.task_supervisor import TaskSupervisor

            task_supervisor = self.registry.get_member_typechecked(
                "task_supervisor", TaskSupervisor
            )
            await task_supervisor.wait("trojan_transport_reader")
