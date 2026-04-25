import json
from pathlib import Path

from linhai.agent.savable_state import SavableState

CONVERSATION_VERSION = "1"


def _get_savable_members(registry) -> dict[str, SavableState]:
    result = {}
    for name, obj in registry.members.items():
        if isinstance(obj, SavableState):
            result[name] = obj
    return result


async def save_conversation(registry, filepath: Path) -> None:
    savable = _get_savable_members(registry)
    data = {
        "version": CONVERSATION_VERSION,
        "members": {name: obj.serialize() for name, obj in savable.items()},
    }
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def restore_conversation(registry, filepath: Path) -> None:
    content = filepath.read_text(encoding="utf-8")
    data = json.loads(content)

    if data.get("version") != CONVERSATION_VERSION:
        raise RuntimeError(
            f"conversation version mismatch: expected {CONVERSATION_VERSION!r}, got {data.get('version')!r}"
        )

    saved_members = set(data.get("members", {}).keys())
    savable = _get_savable_members(registry)
    current_members = set(savable.keys())

    missing = current_members - saved_members
    extra = saved_members - current_members
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing members: {sorted(missing)}")
        if extra:
            parts.append(f"extra members: {sorted(extra)}")
        raise RuntimeError("conversation restore failed: " + ", ".join(parts))

    for name, obj in savable.items():
        obj.restore_from(data["members"][name])

    from linhai.agent.lifecycle import Lifecycle

    lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
    await lifecycle.after_conversation_restore.trigger()
