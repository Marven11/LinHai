from typing import Any, TypeVar, Type, LiteralString
import asyncio

T = TypeVar("T")


# poor man's actor model
class GroupChat:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}
        self.members: dict[str, Any] = {}

    def register_queue(self, name: LiteralString):
        if name in self.queues:
            raise RuntimeError(f"{name!r} exists")
        self.queues[name] = asyncio.Queue()

    def register_member(self, name: LiteralString, obj: Any):
        # 让各个对象在__init__时注册自己
        if name in self.members:
            raise RuntimeError(f"{name!r} exists")
        self.members[name] = obj

    def get_members(self, name: LiteralString, t: Type[T]) -> T:
        if name not in self.members:
            raise RuntimeError(f"{name!r} not exists")
        if not isinstance(self.members[name], t):
            raise RuntimeError(f"{name!r} is not {t}")
        return self.members[name]

    async def send(self, name: LiteralString, message: Any):
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        await self.queues[name].put(message)

    def is_empty(self, name: LiteralString) -> bool:
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        return self.queues[name].empty()

    async def receive(self, name: LiteralString) -> Any:
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        return await self.queues[name].get()
