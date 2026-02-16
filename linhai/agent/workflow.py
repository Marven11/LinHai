"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import cast, List
import time
from dataclasses import dataclass
from linhai.type_hints import LanguageModelMessage
from reprlib import Repr
import linhai
from .base import RuntimeMessage, MessagesListSummerizeMessage, GlobalPrompt
from linhai.markdown_parser import extract_json_blocks
from linhai.llm import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils import CliRuntimeNotice, generate_id
from pathlib import Path
from .conversation import save_cleaned_messages


repr_obj = Repr()
repr_obj.maxstring = 100


@dataclass
class RangeCleanInfo:
    """range_clean_id的验证信息"""

    range_clean_id: str
    message_length: int
    min_safe_id: int
    created_at: float


class RangeCleanManager:
    """管理range_clean_id和对应的验证信息"""

    def __init__(self, group_chat: "linhai.group_chat.GroupChat"):
        group_chat.register_member("range_clean_manager", self)
        self._clean_infos: dict[str, RangeCleanInfo] = {}

    def create_clean_info(
        self, range_clean_id: str, message_length: int, min_safe_id: int
    ) -> RangeCleanInfo:
        """创建验证信息"""
        info = RangeCleanInfo(
            range_clean_id=range_clean_id,
            message_length=message_length,
            min_safe_id=min_safe_id,
            created_at=time.time(),
        )
        self._clean_infos[range_clean_id] = info
        return info

    def get_clean_info(self, range_clean_id: str) -> RangeCleanInfo | None:
        """获取验证信息"""
        return self._clean_infos.get(range_clean_id)

    def remove_clean_info(self, range_clean_id: str):
        """移除验证信息"""
        if range_clean_id in self._clean_infos:
            del self._clean_infos[range_clean_id]

    def is_valid(self, range_clean_id: str) -> bool:
        """检查ID是否有效"""
        return range_clean_id in self._clean_infos


def _prepare_messages_for_compression(agent: "linhai.agent.Agent") -> str:
    """准备消息用于压缩，包括计算显示间隔"""
    messages: List[LanguageModelMessage] = [
        msg.to_llm_message() for msg in agent.message_processor.messages
    ]
    total_messages = len(messages)

    if total_messages < 50:
        max_index = total_messages
    else:
        max_index = total_messages - 50

    if total_messages < 200:
        interval = 1
    else:
        interval = ((max_index - 1) // 200) + 2

    filtered_messages = [
        f"- id: {i} role: {messages[i]['role']!r} content: {repr_obj.repr(messages[i].get('content', None))}"
        for i in range(0, max_index, interval)
    ]

    return "\n".join(filtered_messages)


def _parse_compression_range(full_response: str) -> tuple[int, int]:
    """从LLM响应中解析压缩范围，返回(start_id, end_id)"""
    json_blocks = extract_json_blocks(full_response)

    if len(json_blocks) == 0:
        raise ValueError("没有检测到JSON block")

    range_data = json_blocks[0]
    if not isinstance(range_data, dict):
        raise ValueError("JSON block格式不正确，应为字典")

    start_id = range_data.get("start_id")
    end_id = range_data.get("end_id")

    if start_id is None or end_id is None:
        raise ValueError("JSON block必须包含start_id和end_id字段")

    if not isinstance(start_id, int) or not isinstance(end_id, int):
        raise ValueError("start_id和end_id必须为整数")

    return start_id, end_id


def _validate_compression_range(
    agent: "linhai.agent.Agent", start_id: int, end_id: int
) -> tuple[bool, str]:
    """验证压缩范围的有效性，返回(是否有效, 错误消息)"""
    if start_id < 0 or end_id < 0:
        return False, "消息ID不能为负数"

    if start_id > end_id:
        return False, "起始ID不能大于结束ID"

    range_size = end_id - start_id + 1
    if range_size < 10:
        return False, "压缩范围至少需要10条消息"

    if end_id >= len(agent.message_processor.messages):
        return False, "结束ID超出消息范围"

    return True, ""


async def context_forget_range_step1(
    group_chat: "linhai.group_chat.GroupChat",
) -> ToolResultSuccess | ToolResultFailed:
    """
    压缩范围第一步：生成消息列表总结并返回range_clean_id。
    """
    from .main import Agent

    agent = group_chat.get_member_typechecked("agent", Agent)

    current_message_count = len(agent.message_processor.messages)
    await group_chat.send_if_exists(
        "ui_log",
        CliRuntimeNotice(
            level="INFO",
            content=f"启动历史压缩第一步，当前共有{current_message_count}条消息",
        ),
    )

    await agent.message_processor.filter_messages(
        lambda msg: not isinstance(msg, MessagesListSummerizeMessage)
    )

    messages_summerization = _prepare_messages_for_compression(agent)
    message_length = len(agent.message_processor.messages)

    max_system_index = -1
    for i, msg in enumerate(agent.message_processor.messages):
        if isinstance(msg, (SystemMessage, GlobalPrompt)):
            max_system_index = i
    min_safe_id = 0 if max_system_index == -1 else max_system_index + 1

    range_clean_id = generate_id("rangeclean")
    range_clean_manager = group_chat.get_member_typechecked(
        "range_clean_manager", RangeCleanManager
    )
    range_clean_manager.create_clean_info(range_clean_id, message_length, min_safe_id)

    agent.message_processor.add_new_message(
        MessagesListSummerizeMessage(
            messages_summerization, message_length, range_clean_id
        )
    )

    return ToolResultSuccess(
        content=(
            f"已生成消息列表总结，ID: {range_clean_id}，当前共有{message_length}条消息。"
            "请查看消息列表总结后调用context_forget_range_step2进行删除。"
        )
    )


async def context_forget_range_step2(
    group_chat: "linhai.group_chat.GroupChat",
    range_clean_id: str,
    start_id: int,
    end_id: int,
    description: str,
) -> ToolResultSuccess | ToolResultFailed:
    """
    压缩范围第二步：使用range_clean_id确认删除范围并执行删除。
    """
    from .main import Agent

    agent = group_chat.get_member_typechecked("agent", Agent)

    range_clean_manager = group_chat.get_member_typechecked(
        "range_clean_manager", RangeCleanManager
    )
    info = range_clean_manager.get_clean_info(range_clean_id)
    if info is None:
        return ToolResultFailed(content=f"range_clean_id无效或已过期: {range_clean_id}")

    current_message_count = len(agent.message_processor.messages)
    max_allowed_id = min(info.message_length - 1, current_message_count - 1)
    allowed_range = (info.min_safe_id, max_allowed_id)

    if start_id < allowed_range[0] or start_id > allowed_range[1]:
        return ToolResultFailed(
            content=f"start_id必须在{allowed_range[0]}到{allowed_range[1]}之间"
        )
    if end_id < allowed_range[0] or end_id > allowed_range[1]:
        return ToolResultFailed(
            content=f"end_id必须在{allowed_range[0]}到{allowed_range[1]}之间"
        )

    passed, error_msg = _validate_compression_range(agent, start_id, end_id)
    if not passed:
        return ToolResultFailed(content=f"历史压缩失败：{error_msg}")

    for i, msg in enumerate(agent.message_processor.messages):
        if (
            isinstance(msg, MessagesListSummerizeMessage)
            and msg.range_clean_id == range_clean_id
        ):
            msg.invalidate()
            await agent.message_processor.delete_message_range(i, i)
            break

    deleted_messages = await agent.message_processor.delete_message_range(
        start_id, end_id
    )
    range_clean_manager.remove_clean_info(range_clean_id)

    conversation_dir = group_chat.get_member_typechecked("conversation_folder", Path)
    filepath = save_cleaned_messages(
        conversation_dir, deleted_messages, prefix="range_compress"
    )

    deleted_user_messages = [
        msg.message
        for msg in deleted_messages
        if isinstance(msg, UserMessage) and msg.message
    ]

    if deleted_user_messages:
        user_messages_summary = "\n".join(f"- {msg}" for msg in deleted_user_messages)
        await agent.message_processor.insert_message(
            start_id + 1,
            RuntimeMessage(f"历史压缩已删除以下用户消息：\n{user_messages_summary}"),
        )

    await agent.message_processor.insert_message(
        start_id,
        RuntimeMessage(
            f"这里有一段消息被删除并转储到{filepath}中，以下为总结，请根据总结继续工作: {description}"
        ),
    )

    return ToolResultSuccess(content=f"你使用历史压缩删除（遗忘）了一段消息，被转储到了{filepath}中，请根据**历史压缩总结**明确当前任务继续工作")
