from typing import Generic, TypeVar, Callable, Awaitable

R = TypeVar("R")


class CallbackSlot(Generic[R]):
    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Awaitable[R]]] = []

    def register(self, callback: Callable[..., Awaitable[R]]) -> None:
        self._callbacks.append(callback)


class BroadcastSlot(CallbackSlot[None]):
    async def trigger(self, *args, **kwargs) -> None:
        for callback in self._callbacks:
            await callback(*args, **kwargs)


class ShortCircuitSlot(CallbackSlot[R]):
    async def trigger(self, *args, **kwargs) -> R | None:
        for callback in self._callbacks:
            result = await callback(*args, **kwargs)
            if result is not None:
                return result
        return None


class InterruptSlot(CallbackSlot[bool]):
    async def trigger(self, *args, **kwargs) -> bool:
        for callback in self._callbacks:
            if await callback(*args, **kwargs):
                return True
        return False


class ChainSlot(CallbackSlot[R]):
    def __init__(
        self,
        *,
        chain_arg: int = 0,
        should_stop: Callable[..., bool] | None = None,
    ) -> None:
        super().__init__()
        self._chain_arg = chain_arg
        self._should_stop = should_stop

    async def trigger(self, *args, **kwargs) -> R:
        args_list = list(args)
        for callback in self._callbacks:
            result = await callback(*args_list, **kwargs)
            if result is not None:
                args_list[self._chain_arg] = result
                if self._should_stop is not None and self._should_stop(result):
                    break
        return args_list[self._chain_arg]
