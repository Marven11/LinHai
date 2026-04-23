from __future__ import annotations

from typing import TypedDict, Literal, Union, Type, TypeVar, NotRequired
import copy

T = TypeVar("T")


class DataUpdateEvent(TypedDict):
    action: Literal["insert", "delete", "replace", "concat"]
    keys: list[Union[str, int]]
    value: dict | list | dict | str | int | float | bool | None


class TaggedEvent(TypedDict):
    idx: int
    event: DataUpdateEvent
    gen: NotRequired[int]


def calculate_diff(old, new) -> list[DataUpdateEvent]:
    assert isinstance(old, (dict, list, str, int, float, bool, type(None)))
    assert isinstance(new, (dict, list, str, int, float, bool, type(None)))
    if type(old) != type(new):
        return [DataUpdateEvent(action="replace", keys=[], value=new)]
    if isinstance(old, (int, float, bool, type(None))):
        return (
            [DataUpdateEvent(action="replace", keys=[], value=new)]
            if new != old
            else []
        )

    if isinstance(old, str):
        assert isinstance(new, str)
        if old == new:
            return []
        if new.startswith(old):
            return [
                DataUpdateEvent(action="concat", keys=[], value=new.removeprefix(old))
            ]
        return [DataUpdateEvent(action="replace", keys=[], value=new)]
    if isinstance(old, list):
        assert isinstance(new, list)
        events = [
            DataUpdateEvent(action=e["action"], keys=[i] + e["keys"], value=e["value"])
            for i, (a, b) in enumerate(zip(old, new))
            for e in calculate_diff(a, b)
        ]
        if len(events) <= 3:
            if len(old) == len(new):
                return events
            if len(old) == len(new) - 1:
                return events + [
                    DataUpdateEvent(action="insert", keys=[], value=new[-1])
                ]
        return [DataUpdateEvent(action="replace", keys=[], value=new)]
    if isinstance(old, dict):
        assert isinstance(new, dict)
        keys_old = set(old.keys())
        keys_new = set(new.keys())
        assert all(isinstance(k, str) for k in keys_old)
        assert all(isinstance(k, str) for k in keys_new)
        if keys_old == keys_new:
            return [
                DataUpdateEvent(
                    action=e["action"], keys=[k] + e["keys"], value=e["value"]
                )
                for k in keys_old
                for e in calculate_diff(old[k], new[k])
            ]
        return [DataUpdateEvent(action="replace", keys=[], value=new)]

    assert False


def assertget(value, t: Type[T]) -> T:
    assert isinstance(value, t)
    return value


def update(
    ref: dict | list,
    key: str | int,
    event: DataUpdateEvent,
):
    if isinstance(key, str):
        assert isinstance(ref, dict)
        if event["action"] == "insert":
            assertget(ref[key], list).append(event["value"])
        elif event["action"] == "concat":
            assert isinstance(ref[key], str)
            ref[key] += assertget(event["value"], str)
        elif event["action"] == "replace":
            ref[key] = event["value"]
        elif event["action"] == "delete":
            del ref[key]

    if isinstance(key, int):
        assert isinstance(ref, list)
        if event["action"] == "insert":
            assertget(ref[key], list).append(event["value"])
        elif event["action"] == "concat":
            assert isinstance(ref[key], str)
            ref[key] += assertget(event["value"], str)
        elif event["action"] == "replace":
            ref[key] = event["value"]
        elif event["action"] == "delete":
            del ref[key]


class JsonPublisher:
    def __init__(self, data: dict):
        self.old_data = None
        self._data = data
        self.event_counter = 0
        self._generation = 0

    def calculate_diff(self):

        data = copy.deepcopy(self._data)
        events = [
            TaggedEvent(idx=self.event_counter + i, event=event, gen=self._generation)
            for i, event in enumerate(calculate_diff(self.old_data, data))
        ]
        self.event_counter += len(events)
        self.old_data = data
        return events

    def reset(self) -> TaggedEvent:
        self.old_data = copy.deepcopy(self._data)
        self.event_counter = 0
        self._generation += 1
        return TaggedEvent(
            idx=-1,
            event=DataUpdateEvent(action="replace", keys=[], value=self.old_data),
            gen=self._generation,
        )


class JsonSubscriber:
    def __init__(self):
        self.data = None
        self.event_counter = 0
        self._generation = 0

    def update_root(self, event: DataUpdateEvent):
        if event["action"] == "replace":
            self.data = event["value"]
        elif event["action"] == "insert":
            assert isinstance(self.data, list)
            self.data.append(event["value"])
        elif event["action"] == "concat":
            assert isinstance(self.data, str)
            self.data += assertget(event["value"], str)
        assert event["action"] != "delete", "Event corrupted: root cannot be deleted"
        return

    def update_data(self, event: TaggedEvent):
        if event["idx"] == -1:
            assert (
                event["event"]["action"] == "replace" and event["event"]["keys"] == []
            )
            self.data = event["event"]["value"]
            self.event_counter = 0
            self._generation = event.get("gen", self._generation)
            return
        if event.get("gen", 0) != self._generation:
            return
        if event["idx"] != self.event_counter:
            raise RuntimeError("Some events are missing")
        self.event_counter += 1

        keys = event["event"]["keys"]

        if len(keys) == 0:
            self.update_root(event["event"])
            return

        ref = self.data
        for i, k in enumerate(event["event"]["keys"]):
            if i == len(event["event"]["keys"]) - 1:
                assert isinstance(ref, (dict, list))
                update(ref, k, event["event"])
                return
            if isinstance(k, str):
                ref = assertget(ref, dict)[k]
            if isinstance(k, int):
                ref = assertget(ref, list)[k]

        assert False


def example():
    data = {}
    pub = JsonPublisher(data)
    sub = JsonSubscriber()

    data["bio"] = "litiansuo"
    for e in pub.calculate_diff():
        sub.update_data(e)
    assert sub.data == {"bio": "litiansuo"}

    data["bio"] += " is making some diff"
    for e in pub.calculate_diff():
        sub.update_data(e)
    assert sub.data == {"bio": "litiansuo is making some diff"}, f"{sub.data=}"

    data["info"] = [{"name": "litiansuo", "age": 24}]
    for e in pub.calculate_diff():
        sub.update_data(e)

    print(sub.data)


if __name__ == "__main__":
    example()
