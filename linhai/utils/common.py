from typing import Literal
import secrets
import json
import re
import os
from pydantic import BaseModel

BAD_TOOLCALL = "<bad toolcall>"


class UiNotice(BaseModel):
    """运行时消息数据模型"""

    level: Literal["INFO", "WARNING", "ERROR"]
    content: str


def generate_id(prefix: str) -> str:
    """生成指定格式的ID

    Args:
        prefix: ID前缀，如'terminal'、'largemessage'等

    Returns:
        格式为'<prefix>_<bytes>'的ID，其中bytes是12位hex
    """
    bytes_part = secrets.token_hex(6)
    return f"{prefix}_{bytes_part}"


def simplify_value(value: str | int | float | bool | None | dict | list) -> str:
    json_repr = lambda x: json.dumps(x, ensure_ascii=False)
    if isinstance(value, str):
        if re.match(r"^[/~]|^[a-zA-Z]:\\|^(\./|\.\./)", value) and len(value) >= 20:
            if re.search(r"[,+]", value) and "/" in value[1:]:
                return (
                    json_repr(value[:37] + "...")
                    if len(value) > 40
                    else json_repr(value)
                )
            filename = os.path.basename(value.rstrip("/"))
            suffix = "/" if value.endswith("/") else ""
            return json_repr(".../" + filename + suffix)
        if len(value) > 40:
            return json_repr(value[:37] + "...")
        return json_repr(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return repr(value)
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            simplified_v = simplify_value(v)
            items.append(f"{json_repr(k)}: {simplified_v}")
        if not items:
            return "{}"
        result = "{" + ", ".join(items) + "}"
        if len(result) > 80:
            return "{" + items[0] + ", ...}"
        return result
    if isinstance(value, list):
        if not value:
            return "[]"
        items = [simplify_value(v) for v in value]
        result = "[" + ", ".join(items) + "]"
        if len(result) > 80:
            return "[" + items[0] + ", ...]"
        return result
    return json_repr(value)


def simplify_toolcall_json(toolcall_json: dict) -> str:
    name = toolcall_json.get("name", "")

    arguments = toolcall_json.get("arguments", {})
    if not isinstance(arguments, dict):
        return f"{name}(<not a dict>)"
    simplified_args = []
    for k, v in arguments.items():
        simplified_args.append(f"{k}={simplify_value(v)}")

    if len(simplified_args) >= 3:
        inner = "\n" + "\n".join(f"    {arg}," for arg in simplified_args)
        inner = inner.rstrip(",")
        return f"{name}( {inner}\n)"
    else:
        return f"{name}({', '.join(simplified_args)})"


def cluster_tool_calls(tool_names: list[str]) -> list[tuple[str, int]]:
    seen: dict[str, int] = {}
    order: list[str] = []
    for name in tool_names:
        if name == BAD_TOOLCALL:
            order.append(name)
            continue
        if name not in seen:
            seen[name] = 0
            order.append(name)
        seen[name] += 1
    parts: list[tuple[str, int]] = []
    for name in order:
        if name == BAD_TOOLCALL:
            parts.append((name, 1))
        else:
            parts.append((name, seen[name]))
    return parts


def parse_and_simplify_toolcall(json_str: str) -> str:
    """简化工具调用格式

    即使streamjson没有抛出错误也不一定能保证json格式正确"""
    stripped = json_str.strip()
    if not stripped or stripped[0] != "{":
        return "<parse json error>"
    try:
        toolcall_json = json.loads(stripped)
    except json.JSONDecodeError:
        return "<parse json error>"
    if not isinstance(toolcall_json, dict):
        return "<not a dict>"
    return simplify_toolcall_json(toolcall_json)
