"""对话管理系统，负责对话历史、大消息、secret等的保存。"""

import json
import time
import uuid
from pathlib import Path
from typing import List

from linhai.registry import Registry
from linhai.llm import Message


def register_conversation_folder(registry: Registry) -> Path:
    """注册conversation_folder到registry，创建并返回对话目录路径。

    Args:
        registry: Registry实例

    Returns:
        创建的对话目录路径
    """
    conversation_id = str(uuid.uuid4())
    base_dir = Path.home() / ".local" / "share" / "linhai" / "conversation"
    conversation_dir = base_dir / conversation_id
    conversation_dir.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    (conversation_dir / "cleaned_messages").mkdir(exist_ok=True)
    (conversation_dir / "large_messages").mkdir(exist_ok=True)
    (conversation_dir / "long_toolcall").mkdir(exist_ok=True)
    (conversation_dir / "secret_intercepted").mkdir(exist_ok=True)

    registry.register_member("conversation_folder", conversation_dir)
    return conversation_dir


def save_context(conversation_dir: Path, messages: List[Message]) -> Path:
    """保存消息历史到context.json。

    Args:
        conversation_dir: 对话目录路径
        messages: 消息列表

    Returns:
        保存的文件路径
    """
    context_file = conversation_dir / "context.json"

    history_data = [
        {"type": msg.__class__.__name__, "data": msg.to_json()} for msg in messages
    ]

    with open(context_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    return context_file


def save_cleaned_messages(
    conversation_dir: Path, messages: List[Message], prefix: str
) -> Path:
    """保存被清理的消息到cleaned_messages目录。

    Args:
        conversation_dir: 对话目录路径
        messages: 被清理的消息列表
        prefix: 文件名前缀

    Returns:
        保存的文件路径
    """
    timestamp = int(time.time())
    filename = f"{prefix}_{timestamp}.json"
    cleaned_messages_dir = conversation_dir / "cleaned_messages"
    cleaned_messages_dir.mkdir(parents=True, exist_ok=True)
    filepath = cleaned_messages_dir / filename

    history_data = [
        {"type": msg.__class__.__name__, "data": msg.to_json()} for msg in messages
    ]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    return filepath


def save_large_message_chunk(
    conversation_dir: Path, content: str, chunk_index: int
) -> Path:
    """保存大消息分块到large_messages目录。

    Args:
        conversation_dir: 对话目录路径
        content: 消息内容
        chunk_index: 分块索引

    Returns:
        保存的文件路径
    """
    timestamp = int(time.time())
    filename = f"large_message_{timestamp}_{chunk_index}.txt"
    filepath = conversation_dir / "large_messages" / filename

    filepath.write_text(content, encoding="utf-8")
    return filepath


def save_long_toolcall_output(
    conversation_dir: Path, content: str, tool_name: str, part_index: int | None = None
) -> Path:
    """保存大工具输出到long_toolcall目录。

    Args:
        conversation_dir: 对话目录路径
        content: 输出内容
        tool_name: 工具名称
        part_index: 分块索引，None表示不分块

    Returns:
        保存的文件路径
    """
    timestamp = int(time.time())
    if part_index is not None:
        filename = f"{tool_name}_{timestamp}_part{part_index}.txt"
    else:
        filename = f"{tool_name}_{timestamp}.txt"
    filepath = conversation_dir / "long_toolcall" / filename

    filepath.write_text(content, encoding="utf-8")
    return filepath


def save_secret_intercepted(
    conversation_dir: Path, content: str, tool_name: str
) -> Path:
    """保存被拦截的含secret内容到secret_intercepted目录。

    Args:
        conversation_dir: 对话目录路径
        content: 被拦截的内容
        tool_name: 工具名称

    Returns:
        保存的文件路径
    """
    timestamp = int(time.time())
    filename = f"secret_intercepted_{timestamp}_{tool_name}.txt"
    filepath = conversation_dir / "secret_intercepted" / filename

    filepath.write_text(content, encoding="utf-8")
    return filepath
