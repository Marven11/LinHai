"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import cast
from reprlib import Repr
import asyncio
import json

import linhai
from .base import RuntimeMessage, CompressRangeRequest, GlobalMemory
from linhai.markdown_parser import extract_json_blocks
from linhai.llm import (
    ChatMessage,
    SystemMessage,
)

repr_obj = Repr()
repr_obj.maxstring = 100


async def compress_history_range(agent: "linhai.agent.Agent") -> str:
    """
    压缩指定范围的历史消息以减少上下文长度。

    通过提示LLM输出要压缩的消息范围（start_id和end_id），
    然后删除指定范围内的消息。
    """

    threshold_info = agent.get_threshold_info()
    if threshold_info:
        soft, _hard, used, _remaining, taken = threshold_info
        if used < soft:
            agent.message_processor.append_message(
                RuntimeMessage("当前token占用没有超过软限制，禁止删除消息")
            )
            return "历史压缩未执行：token占用未超过软限制"
        if taken < 0.2:
            agent.message_processor.append_message(
                RuntimeMessage(
                    f"当前token占用小于20%，仅为{taken*100:.2f}%，禁止删除消息"
                )
            )
            return f"历史压缩未执行：token占用仅为{taken*100:.2f}%"

    # 使用filter_messages方法过滤CompressRangeRequest消息
    agent.message_processor.filter_messages(lambda msg: not isinstance(msg, CompressRangeRequest))

    messages = [msg.to_llm_message() for msg in agent.message_processor.messages]
    messages_summerization = "\n".join(
        f"- id: {i} role: {msg['role']!r} content: {repr_obj.repr(msg.get('content', None))}"
        for i, msg in enumerate(messages)
    )

    agent.message_processor.append_message(
        CompressRangeRequest(messages_summerization, len(agent.message_processor.messages))
    )

    # 生成响应，让LLM输出范围
    answer = await agent.generate_response(
        enable_compress=False, disable_waiting_user_warning=True
    )
    chat_message = cast(ChatMessage, answer.get_message())
    full_response = chat_message.message

    json_blocks = []
    try:
        # 解析LLM输出，提取JSON块
        json_blocks = extract_json_blocks(full_response)
    except json.JSONDecodeError as exc:
        agent.message_processor.append_message(
            RuntimeMessage(f"错误：非法JSON: {str(exc)}")
        )
        return "历史压缩失败：JSON格式错误"
    except ValueError as exc:
        agent.message_processor.append_message(
            RuntimeMessage(f"错误：处理压缩范围时发生异常: {str(exc)}")
        )
        return "历史压缩失败：处理异常"

    if len(json_blocks) == 0:
        agent.message_processor.append_message(
            RuntimeMessage(
                "错误：没有检测到JSON block，请确保输出包含正确的JSON格式范围数据"
            )
        )
        return "历史压缩失败：未检测到JSON块"

    # 提取第一个JSON块
    range_data = json_blocks[0]
    if not isinstance(range_data, dict):
        agent.message_processor.append_message(RuntimeMessage("错误：JSON block 格式不正确，应为字典"))
        return "历史压缩失败：JSON格式不正确"

    start_id = range_data.get("start_id")
    end_id = range_data.get("end_id")

    if start_id is None or end_id is None:
        agent.message_processor.append_message(
            RuntimeMessage("错误：JSON block 必须包含 start_id 和 end_id 字段")
        )
        return "历史压缩失败：缺少start_id或end_id字段"

    # 验证参数类型
    if not isinstance(start_id, int) or not isinstance(end_id, int):
        agent.message_processor.append_message(RuntimeMessage("错误：start_id 和 end_id 必须为整数"))
        return "历史压缩失败：start_id和end_id必须为整数"

    # 通过检查消息类来确定最小安全ID，保护系统消息
    max_system_index = -1
    for i, msg in enumerate(agent.message_processor.messages):
        if isinstance(msg, (SystemMessage, GlobalMemory)):
            max_system_index = i

    if max_system_index == -1:
        min_safe_id = 0
    else:
        min_safe_id = max_system_index + 1

    if start_id < min_safe_id:
        agent.message_processor.append_message(
            RuntimeMessage(
                f"错误：start_id不能小于{min_safe_id},已经更正为{min_safe_id}"
            )
        )
        start_id = min_safe_id

    # 参数验证
    if start_id < 0 or end_id < 0:
        agent.message_processor.append_message(RuntimeMessage("错误：消息ID不能为负数"))
        return "历史压缩失败：消息ID不能为负数"

    if start_id > end_id:
        agent.message_processor.append_message(RuntimeMessage("错误：起始ID不能大于结束ID"))
        return "历史压缩失败：起始ID不能大于结束ID"

    # 检查范围大小，至少10条消息
    range_size = end_id - start_id + 1
    if range_size < 10:
        agent.message_processor.append_message(RuntimeMessage("错误：压缩范围至少需要10条消息"))
        return "历史压缩失败：压缩范围至少需要10条消息"

    # 检查删除比例是否小于总消息数量的30%
    total_messages = len(agent.message_processor.messages)
    delete_ratio = range_size / total_messages
    if delete_ratio < 0.3:
        agent.message_processor.append_message(
            RuntimeMessage(
                f"警告：你删除的消息数量（{range_size}条）小于总消息数量的30%（{total_messages}条），"
                f"删除比例仅为{delete_ratio*100:.1f}%。建议删除更多消息。"
            )
        )

    # 检查范围是否有效
    if end_id >= len(agent.message_processor.messages):
        agent.message_processor.append_message(RuntimeMessage("错误：结束ID超出消息范围"))
        return "历史压缩失败：结束ID超出消息范围"

    # 收集被删除的用户消息内容
    deleted_user_messages = []
    for msg in agent.message_processor.messages[start_id : end_id + 1]:
        if isinstance(msg, ChatMessage) and msg.role == "user":
            content = msg.message
            if content:
                deleted_user_messages.append(content)

    # 使用 delete_message_range 方法删除指定范围的消息
    deleted_messages = agent.message_processor.delete_message_range(start_id, end_id)
    agent.message_processor.append_message(
        RuntimeMessage(f"历史压缩已删除{range_size}条消息（从{start_id}到{end_id}）")
    )

    # 如果删除了用户消息，添加额外的消息包含被删除的用户消息内容
    if deleted_user_messages:
        user_messages_summary = "\n".join(f"- {msg}" for msg in deleted_user_messages)
        agent.message_processor.insert_message(
            start_id + 1,
            RuntimeMessage(f"历史压缩已删除以下用户消息：\n{user_messages_summary}"),
        )

    # 使用filter_messages方法过滤CompressRangeRequest消息
    agent.message_processor.filter_messages(lambda msg: not isinstance(msg, CompressRangeRequest))
    return "历史压缩成功完成，现在请继续工作！"
