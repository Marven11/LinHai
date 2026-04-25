from typing import Protocol, runtime_checkable


@runtime_checkable
class SavableState(Protocol):
    def serialize(self) -> dict: ...

    def restore_from(self, data: dict) -> None: ...
