"""基于asyncio.Queue的异步队列，支持类似Golang中chan的操作"""

import asyncio
from typing import Any, AsyncIterator, Generic, Tuple, TypeVar

T = TypeVar("T")


class QueueClosed(Exception):
    """队列已关闭异常"""


class Queue(Generic[T]):
    """异步队列类，支持类似Golang chan的操作"""

    def __init__(self, maxsize: int = 0):
        self._queue = asyncio.Queue(maxsize)
        self._closed = False

    async def put(self, item: T) -> None:
        if self._closed:
            raise QueueClosed("Cannot put to a closed queue")
        await self._queue.put(item)

    async def get(self) -> T:
        """从队列获取元素"""
        if self._closed and self._queue.empty():
            raise QueueClosed("Queue is closed and empty")
        return await self._queue.get()

    def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()


async def select(*queues: Queue) -> AsyncIterator[Tuple[Any, int]]:
    """
    同时等待多个队列，直到所有队列关闭

    返回一个异步迭代器，每次迭代返回一个元组（数据，原始队列索引）

    当所有队列都关闭时，停止迭代
    """
    original_indices = {id(q): idx for idx, q in enumerate(queues)}
    active_queues = list(queues)

    while active_queues:
        tasks = [asyncio.create_task(q.get()) for q in active_queues]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            try:
                item = task.result()
                q_index = tasks.index(task)
                q = active_queues[q_index]
                yield (item, original_indices[id(q)])
            except QueueClosed:
                q_index = tasks.index(task)
                q = active_queues[q_index]
                active_queues.pop(q_index)

        # 取消未完成的任务
        for task in pending:
            task.cancel()


__all__ = ["Queue", "QueueClosed", "select"]
