import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

if TYPE_CHECKING:
    from linhai.registry import Registry

from textual.app import App
from textual.worker import Worker


@runtime_checkable
class TaskSupervisor(Protocol):
    def create_supervised_task(
        self, name: str, fn: Callable[[], Coroutine[None, None, None]]
    ) -> None: ...

    async def wait(self, name: str) -> None: ...

    def cancel(self, name: str) -> None: ...

    async def run_with_timeout(
        self, coro: Coroutine[Any, Any, Any], timeout: float
    ) -> Tuple[bool, Any]: ...


class PlainTaskSupervisor:
    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def create_supervised_task(
        self, name: str, fn: Callable[[], Coroutine[None, None, None]]
    ) -> None:
        task = asyncio.create_task(fn(), name=name)
        self.tasks[name] = task

    async def wait(self, name: str) -> None:
        if name not in self.tasks:
            raise RuntimeError(f"Task {name} not found")
        await self.tasks[name]

    def cancel(self, name: str) -> None:
        if name not in self.tasks:
            raise RuntimeError(f"Task {name} not found")
        self.tasks[name].cancel()

    async def run_with_timeout(
        self, coro: Coroutine[Any, Any, Any], timeout: float
    ) -> Tuple[bool, Any]:
        task = asyncio.create_task(coro)
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if task in done:
            return True, task.result()
        task.cancel()
        return False, None


class TextualTaskSupervisor:
    def __init__(self, app: App, registry: "Registry") -> None:
        self.app = app
        self.workers: dict[str, Worker[None]] = {}
        registry.register_member("task_supervisor", self)

    def create_supervised_task(
        self, name: str, fn: Callable[[], Coroutine[None, None, None]]
    ) -> None:
        worker = self.app.run_worker(fn(), name=name)
        self.workers[name] = worker

    async def wait(self, name: str) -> None:
        if name not in self.workers:
            raise RuntimeError(f"Worker {name} not found")
        await self.workers[name].wait()

    def cancel(self, name: str) -> None:
        if name not in self.workers:
            raise RuntimeError(f"Worker {name} not found")
        self.workers[name].cancel()

    async def run_with_timeout(
        self, coro: Coroutine[Any, Any, Any], timeout: float
    ) -> Tuple[bool, Any]:
        task = asyncio.create_task(coro)
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if task in done:
            return True, task.result()
        task.cancel()
        return False, None
