"""
> poor man's actor model

GroupChat通信框架，实现多个单例之间的通信，解耦设计
管理数据
    - GroupChat管理以下两种数据
        - 单例
        - queue:
            - 每个queue都有相应的接收者接收并处理数据
            - 一个queue只有**一个**接收者!
            - queue的名字表示其中的数据类型
注册
    - 每个单例在初始化时获得GroupChat实例，此时注册自己以及需要从中读取数据的queue
        - 不要在其他地方注册：如果在初始函数外注册单例则会导致RuntimeError!
使用
    - 项目使用GroupChat解耦两类数据传递过程：
        - 消息发布：消息从多个来源传入一个queue，由专门的处理者接收
        - 函数调用：获得单例并调用
    - 在需要处理单例之间的通信时优先使用GroupChat！
        - 不要使用循环持有引用或者其他更糟的设计模式！
"""

from typing import Any, TypeVar, Type, LiteralString
import asyncio

T = TypeVar("T")


class GroupChat:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}
        self.members: dict[str, Any] = {}

    def register_queue(self, name: LiteralString):
        if name in self.queues:
            raise RuntimeError(f"{name!r} exists")
        self.queues[name] = asyncio.Queue()

    def register_member(self, name: LiteralString, obj: Any):

        if name in self.members:
            raise RuntimeError(f"{name!r} exists")
        self.members[name] = obj

    def get_members(self, name: LiteralString, t: Type[T]) -> T:
        if name not in self.members:
            raise RuntimeError(f"{name!r} not exists")
        if not isinstance(self.members[name], t):
            raise RuntimeError(f"{name!r} is not {t}")
        return self.members[name]

    def has_member(self, name: LiteralString) -> bool:
        """检查指定的成员是否存在"""
        return name in self.members

    async def send(self, name: LiteralString, message: Any):
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        await self.queues[name].put(message)

    async def send_if_exists(self, name: LiteralString, message: Any):
        if name in self.queues:
            await self.queues[name].put(message)

    def is_empty(self, name: LiteralString) -> bool:
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        return self.queues[name].empty()

    async def receive(self, name: LiteralString) -> Any:
        if name not in self.queues:
            raise RuntimeError(f"{name!r} not exists")
        return await self.queues[name].get()
