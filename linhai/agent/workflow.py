"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import cast, List
from linhai.type_hints import LanguageModelMessage
from reprlib import Repr
import linhai
from .base import RuntimeMessage, CompressRangeRequest, GlobalMemory
from linhai.markdown_parser import extract_json_blocks
from linhai.llm import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils import CliRuntimeNotice
from linhai.agent.conversation import get_current_conversation


repr_obj = Repr()
repr_obj.maxstring = 100


def _prepare_messages_for_compression(agent: "linhai.agent.Agent") -> str:
    """准备消息用于压缩，包括计算显示间隔"""
    messages: List[LanguageModelMessage] = [
        msg.to_llm_message() for msg in agent.message_processor.messages
    ]
    total_messages = len(messages)

    interval = 1 if total_messages < 200 else (total_messages + 199) // 200
    max_index = total_messages - 50 if total_messages >= 50 else total_messages

    filtered_messages = [
        f"- id: {i} role: {messages[i]['role']!r} content: {repr_obj.repr(messages[i].get('content', None))}"
        for i in range(0, max_index, interval)
    ]

    if len(filtered_messages) > 50:
        filtered_messages = filtered_messages[:50]

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
    max_system_index = -1
    for i, msg in enumerate(agent.message_processor.messages):
        if isinstance(msg, (SystemMessage, GlobalMemory)):
            max_system_index = i

    min_safe_id = 0 if max_system_index == -1 else max_system_index + 1

    if start_id < min_safe_id:
        return False, f"start_id不能小于{min_safe_id}"

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


async def context_range_compress(
    agent: "linhai.agent.Agent",
) -> ToolResultSuccess | ToolResultFailed:
    """
    压缩指定范围的历史消息以减少上下文长度。

    通过提示LLM输出要压缩的消息范围（start_id和end_id），
    然后删除指定范围内的消息。
    """

    current_message_count = len(agent.message_processor.messages)
    await agent.group_chat.send_if_exists(
        "ui_log",
        CliRuntimeNotice(
            level="INFO", content=f"启动历史压缩，当前共有{current_message_count}条消息"
        ),
    )

    await agent.message_processor.filter_messages(
        lambda msg: not isinstance(msg, CompressRangeRequest)
    )

    messages_summerization = _prepare_messages_for_compression(agent)
    agent.message_processor.add_new_message(
        CompressRangeRequest(
            messages_summerization, len(agent.message_processor.messages)
        )
    )

    try:
        answer = await agent.generate_response(
            enable_compress=False, disable_waiting_user_warning=True
        )
        assistant_message = cast(AssistantMessage, answer.get_message())
        full_response = assistant_message.message

        summary_message_index = len(agent.message_processor.messages) - 1
        summary_content = full_response

        try:
            start_id, end_id = _parse_compression_range(full_response)
        except ValueError as exc:
            agent.message_processor.add_new_message(RuntimeMessage(f"错误：{str(exc)}"))
            return ToolResultFailed(content=f"历史压缩失败：{str(exc)}")

        passed, error_msg = _validate_compression_range(agent, start_id, end_id)
        if not passed:
            agent.message_processor.add_new_message(RuntimeMessage(error_msg))
            return ToolResultFailed(content=f"历史压缩失败：{error_msg}")

        if summary_message_index >= 0:
            await agent.message_processor.delete_message_range(
                summary_message_index, summary_message_index
            )

        deleted_messages = await agent.message_processor.delete_message_range(
            start_id, end_id
        )

        conv = get_current_conversation()
        conv.save_cleaned_messages(deleted_messages, prefix="range_compress")

        deleted_user_messages = [
            msg.message
            for msg in deleted_messages
            if isinstance(msg, UserMessage) and msg.message
        ]

        if deleted_user_messages:
            user_messages_summary = "\n".join(
                f"- {msg}" for msg in deleted_user_messages
            )
            await agent.message_processor.insert_message(
                start_id + 1,
                RuntimeMessage(
                    f"历史压缩已删除以下用户消息：\n{user_messages_summary}"
                ),
            )

        wrapped_summary = f"历史压缩总结（已删除的消息范围：{start_id}-{end_id}）：\n{summary_content}"
        await agent.message_processor.insert_message(
            start_id,
            RuntimeMessage(wrapped_summary),
        )

        return ToolResultSuccess(
            content=(
                "历史压缩成功完成，现在请继续工作！"
                "注意：每次进行历史压缩都需要重新调用compress_history_range工具！"
                "注意：历史压缩不能仅输出总结和ID，必须先调用工具！"
            )
        )
    finally:

        await agent.message_processor.filter_messages(
            lambda msg: not isinstance(msg, CompressRangeRequest)
        )
        agent.last_token_usage = None
