"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import cast
from reprlib import Repr

import linhai
from .base import RuntimeMessage, CompressRangeRequest, GlobalMemory
from linhai.markdown_parser import extract_json_blocks
from linhai.llm import (
    ChatMessage,
    SystemMessage,
)

repr_obj = Repr()
repr_obj.maxstring = 100


def _check_token_threshold(agent: "linhai.agent.Agent") -> tuple[bool, str]:
    """检查token阈值，返回(是否通过, 错误消息)"""
    threshold_info = agent.get_threshold_info()
    if not threshold_info:
        return True, ""
    
    soft, _hard, used, _remaining, taken = threshold_info
    if used < soft:
        return False, "当前token占用没有超过软限制，禁止删除消息"
    
    if taken < 0.2:
        return False, f"当前token占用小于20%，仅为{taken*100:.2f}%，禁止删除消息"
    
    return True, ""


def _prepare_messages_for_compression(agent: "linhai.agent.Agent") -> str:
    """准备消息摘要供LLM选择压缩范围"""
    messages = [msg.to_llm_message() for msg in agent.message_processor.messages]
    return "\n".join(
        f"- id: {i} role: {msg['role']!r} content: {repr_obj.repr(msg.get('content', None))}"
        for i, msg in enumerate(messages)
    )


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
    # 通过检查消息类来确定最小安全ID，保护系统消息
    max_system_index = -1
    for i, msg in enumerate(agent.message_processor.messages):
        if isinstance(msg, (SystemMessage, GlobalMemory)):
            max_system_index = i
    
    min_safe_id = 0 if max_system_index == -1 else max_system_index + 1
    
    if start_id < min_safe_id:
        return False, f"start_id不能小于{min_safe_id},已经更正为{min_safe_id}"
    
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


def _check_delete_ratio_warning(agent: "linhai.agent.Agent", start_id: int, end_id: int) -> str | None:
    """检查删除比例是否需要警告，返回警告消息或None"""
    range_size = end_id - start_id + 1
    total_messages = len(agent.message_processor.messages)
    delete_ratio = range_size / total_messages
    
    if delete_ratio < 0.3:
        return (
            f"警告：你删除的消息数量（{range_size}条）小于总消息数量的30%（{total_messages}条），"
            f"删除比例仅为{delete_ratio*100:.1f}%。建议删除更多消息。"
        )
    return None


def _collect_deleted_user_messages(agent: "linhai.agent.Agent", start_id: int, end_id: int) -> list[str]:
    """收集被删除的用户消息内容"""
    deleted_user_messages = []
    for msg in agent.message_processor.messages[start_id : end_id + 1]:
        if isinstance(msg, ChatMessage) and msg.role == "user":
            content = msg.message
            if content:
                deleted_user_messages.append(content)
    return deleted_user_messages


def _process_compression_range(agent: "linhai.agent.Agent", full_response: str) -> tuple[int, int] | str:
    """处理压缩范围的解析和验证，返回(start_id, end_id)或错误消息"""
    try:
        start_id, end_id = _parse_compression_range(full_response)
    except ValueError as exc:
        agent.message_processor.append_message(RuntimeMessage(f"错误：{str(exc)}"))
        return f"历史压缩失败：{str(exc)}"

    # 验证压缩范围
    passed, error_msg = _validate_compression_range(agent, start_id, end_id)
    if not passed:
        agent.message_processor.append_message(RuntimeMessage(error_msg))
        return f"历史压缩失败：{error_msg}"

    return start_id, end_id


async def _execute_message_deletion(agent: "linhai.agent.Agent", start_id: int, end_id: int) -> None:
    """执行消息删除和相关操作"""
    # 检查删除比例警告
    warning_msg = _check_delete_ratio_warning(agent, start_id, end_id)
    if warning_msg:
        agent.message_processor.append_message(RuntimeMessage(warning_msg))

    # 收集被删除的用户消息内容
    deleted_user_messages = _collect_deleted_user_messages(agent, start_id, end_id)

    # 使用delete_message_range方法删除指定范围的消息
    range_size = end_id - start_id + 1
    deleted_messages = await agent.message_processor.delete_message_range(start_id, end_id)
    agent.message_processor.append_message(
        RuntimeMessage(f"历史压缩已删除{range_size}条消息（从{start_id}到{end_id}）")
    )

    # 如果删除了用户消息，添加额外的消息包含被删除的用户消息内容
    if deleted_user_messages:
        user_messages_summary = "\n".join(f"- {msg}" for msg in deleted_user_messages)
        await agent.message_processor.insert_message(
            start_id + 1,
            RuntimeMessage(f"历史压缩已删除以下用户消息：\n{user_messages_summary}"),
        )


async def compress_history_range(agent: "linhai.agent.Agent") -> str:
    """
    压缩指定范围的历史消息以减少上下文长度。

    通过提示LLM输出要压缩的消息范围（start_id和end_id），
    然后删除指定范围内的消息。
    """

    # 检查token阈值
    passed, error_msg = _check_token_threshold(agent)
    if not passed:
        agent.message_processor.append_message(RuntimeMessage(error_msg))
        return f"历史压缩未执行：{error_msg}"

    # 使用filter_messages方法过滤CompressRangeRequest消息
    await agent.message_processor.filter_messages(lambda msg: not isinstance(msg, CompressRangeRequest))

    # 准备消息摘要
    messages_summerization = _prepare_messages_for_compression(agent)
    agent.message_processor.append_message(
        CompressRangeRequest(messages_summerization, len(agent.message_processor.messages))
    )

    try:
        # 生成响应，让LLM输出范围
        answer = await agent.generate_response(
            enable_compress=False, disable_waiting_user_warning=True
        )
        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message

        # 记录总结消息的位置（最后一条消息）
        summary_message_index = len(agent.message_processor.messages) - 1
        summary_content = full_response

        # 使用新函数处理压缩范围
        range_result = _process_compression_range(agent, full_response)
        if isinstance(range_result, str):
            return range_result  # 返回错误消息
        
        start_id, end_id = range_result

        # 删除总结消息（在删除范围之前处理，以避免索引变化）
        if summary_message_index >= 0:
            await agent.message_processor.delete_message_range(summary_message_index, summary_message_index)

        # 使用新函数执行消息删除操作
        await _execute_message_deletion(agent, start_id, end_id)

        # 将总结内容包裹后插入到被删除消息的起始位置
        wrapped_summary = f"历史压缩总结（已删除的消息范围：{start_id}-{end_id}）：\n{summary_content}"
        await agent.message_processor.insert_message(
            start_id,
            RuntimeMessage(wrapped_summary),
        )

        return "历史压缩成功完成，现在请继续工作！"
    finally:
        # 使用filter_messages方法过滤CompressRangeRequest消息
        await agent.message_processor.filter_messages(lambda msg: not isinstance(msg, CompressRangeRequest))
        # 清掉token用量以防立马重新开启compress_history_range
        # [TODO]: 现在硬阈值开启compress_history_range的逻辑完全基于token用量，需要修改
        agent.last_token_usage = None
