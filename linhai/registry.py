"""
> poor man's actor model

Registry通信框架，实现多个单例之间的通信，解耦设计
管理数据
    - Registry管理以下两种数据
        - 单例
        - queue:
            - 每个queue都有相应的接收者接收并处理数据
            - 一个queue只有**一个**接收者!
            - queue的名字表示其中的数据类型
注册
    - 每个单例在初始化时获得Registry实例，此时注册自己以及需要从中读取数据的queue
        - 不要在其他地方注册：如果在初始函数外注册单例则会导致RuntimeError!
使用
    - 项目使用Registry解耦两类数据传递过程：
        - 消息发布：消息从多个来源传入一个queue，由专门的处理者接收
        - 函数调用：获得单例并调用
    - 在需要处理单例之间的通信时优先使用Registry！
        - 不要使用循环持有引用或者其他更糟的设计模式！

在传输数据时，尽量使用自定义类（dataclass/pydantic）以减少心智负担，避免使用字典。
例如，SubAgent现在使用wrapper类（SubAgentAnswerTokenWrapper, SubAgentAnswerCompleteWrapper）来传输消息。
"""

from typing import Any, TypeVar, Type, LiteralString, Callable
import asyncio

T = TypeVar("T")


class Registry:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}
        self.members: dict[str, Any] = {}
        self._postinit_callbacks: list[Callable[[], None]] = []
        self._postinit_called = False

    def register_queue(self, name: LiteralString):
        if name in self.queues:
            raise RuntimeError(f"{name!r} exists")
        self.queues[name] = asyncio.Queue()

    def register_member(self, name: LiteralString, obj: Any):

        if name in self.members:
            raise RuntimeError(f"{name!r} exists")
        self.members[name] = obj

    def get_member_typechecked(self, name: LiteralString, t: Type[T]) -> T:
        """注意：t用来动态检测类型，保证拿到的数据类型正确

        这个函数用来解决循环引用的问题和交叉持有带来的无法初始化的问题

        这个函数的正确用法是：
            - 有必要的话，在函数内import对应的类型传给t参数
            - 每次使用数据都动态获取，而不是保存在属性中！
        """
        # it's so FUCKED up that we write prompt in the error message
        if name not in self.members:
            raise RuntimeError(
                f"{name!r}未初始化，检查以下问题: "
                "1. 是否在__init__函数中调用此函数，如果有则说明你在提前获取其他对象！必须阅读本文件的注释，在使用其他对象时才获取！"
                "2. 是否是unittest错误，如果是则说明你的unittest没有注册此对象，必须在unittest中完整构造这个对象！"
            )
        if not isinstance(self.members[name], t):
            raise RuntimeError(
                f"{name!r}不是类型{t}，检查以下问题："
                "1. 是否将Mock类传入了此类"
                "2. 是否传入了正确的类"
            )
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

    def add_postinit(self, callback: Callable[[], None]) -> None:
        """注册一个后初始化回调函数

        回调函数将在所有对象都初始化完毕后被调用，用来执行需要访问其他对象的初始化操作。
        """
        if self._postinit_called:
            raise RuntimeError("postinit已经调用，无法再添加回调")
        self._postinit_callbacks.append(callback)

    def call_postinit(self) -> None:
        """调用所有后初始化回调函数"""
        if self._postinit_called:
            raise RuntimeError("postinit已经调用过")
        for callback in self._postinit_callbacks:
            callback()
        self._postinit_called = True
