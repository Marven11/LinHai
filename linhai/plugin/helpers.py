"""Plugin共享的辅助函数。"""

from pathlib import Path
import reprlib
import time
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    TypeAlias,
    Union,
    Literal,
    TYPE_CHECKING,
)

from linhai.tool.base import ToolCallResultMessage, FileContentToolResult

if TYPE_CHECKING:
    from linhai.agent.main import Agent as linhai_agent

JsonValue: TypeAlias = Union[
    str, int, float, bool, List["JsonValue"], Dict[str, "JsonValue"], None
]

READ_FILE_COMMANDS = {
    "cat",
    "nl",
    "sed",
    "awk",
    "grep",
    "rg",
    "head",
    "tail",
    "more",
    "less",
}


async def is_small_file(filepath: str) -> bool:
    """检查文件是否过小。"""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
            char_count = len(content)
            line_count = content.count(b"\n")
            return char_count < 40000 and line_count < 2000
    except (FileNotFoundError, PermissionError, OSError):
        return False


async def is_already_read(agent: "linhai_agent", filepath: str) -> bool:
    """检查文件是否已被读取（最新FileContentMessage内容与硬盘文件内容相同）。"""
    try:
        abs_path = Path(filepath).resolve()
        with open(abs_path, "rb") as f:
            disk_content = f.read().decode("utf-8", errors="ignore")
    except (OSError, ValueError, UnicodeDecodeError):
        return False

    latest_message = None
    for msg in reversed(list(agent.message_processor.get_messages())):
        if isinstance(msg, ToolCallResultMessage) and isinstance(
            msg.result, FileContentToolResult
        ):
            try:
                if Path(msg.result.filepath).resolve() == abs_path:
                    latest_message = msg.result
                    break
            except (OSError, ValueError):
                continue

    if latest_message and latest_message.content == disk_content:
        return True
    return False


def is_existing_file(path_str: str) -> bool:
    """检查路径是否为存在的文件。"""
    try:
        path = Path(path_str)
        return path.is_file()
    except (OSError, ValueError):
        return False
