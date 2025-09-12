"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import cast
from reprlib import Repr

import linhai
from linhai.agent_base import RuntimeMessage, CompressRangeRequest, GlobalMemory
from linhai.markdown_parser import extract_json_blocks
from linhai.llm import (
    ChatMessage,
    SystemMessage,
)

repr_obj = Repr(maxstring=100)


async def compress_history_range(agent: "linhai.agent.Agent") -> bool:
    """
    压缩指定范围的历史消息以减少上下文长度。

    通过提示LLM输出要压缩的消息范围（start_id和end_id），
    然后删除指定范围内的消息。
    """

    agent.messages = [
        (
            RuntimeMessage("已经失效的历史压缩prompt")
            if isinstance(msg, CompressRangeRequest)
            else msg
        )
        for msg in agent.messages
    ]

    messages = [msg.to_llm_message() for msg in agent.messages]
    messages_summerization = "\n".join(
        f"- id: {i} role: {msg["role"]!r} content: {repr_obj.repr(msg.get('content', None))}"
        for i, msg in enumerate(messages)
    )

    agent.messages.append(
        CompressRangeRequest(messages_summerization, len(agent.messages))
    )

    # 生成响应，让LLM输出范围
    answer = await agent.generate_response(
        enable_compress=False, disable_waiting_user_warning=True
    )
    chat_message = cast(ChatMessage, answer.get_message())
    full_response = chat_message.message

    try:
        # 解析LLM输出，提取JSON块
        json_blocks = extract_json_blocks(full_response)
        if len(json_blocks) == 0:
            agent.messages.append(
                RuntimeMessage(
                    "错误：没有检测到JSON block，请确保输出包含正确的JSON格式范围数据"
                )
            )
            return True

        # 提取第一个JSON块
        range_data = json_blocks[0]
        if not isinstance(range_data, dict):
            agent.messages.append(
                RuntimeMessage("错误：JSON block 格式不正确，应为字典")
            )
            return True

        start_id = range_data.get("start_id")
        end_id = range_data.get("end_id")

        if start_id is None or end_id is None:
            agent.messages.append(
                RuntimeMessage("错误：JSON block 必须包含 start_id 和 end_id 字段")
            )
            return True

        # 验证参数类型
        if not isinstance(start_id, int) or not isinstance(end_id, int):
            agent.messages.append(RuntimeMessage("错误：start_id 和 end_id 必须为整数"))
            return True

        # 通过检查消息类来确定最小安全ID，保护系统消息
        max_system_index = -1
        for i, msg in enumerate(agent.messages):
            if isinstance(msg, (SystemMessage, GlobalMemory)):
                max_system_index = i

        if max_system_index == -1:
            min_safe_id = 0
        else:
            min_safe_id = max_system_index + 1

        if start_id < min_safe_id:
            agent.messages.append(
                RuntimeMessage(
                    f"错误：start_id不能小于{min_safe_id},已经更正为{min_safe_id}"
                )
            )
            start_id = min_safe_id

        # 参数验证
        if start_id < 0 or end_id < 0:
            agent.messages.append(RuntimeMessage("错误：消息ID不能为负数"))
            return True

        if start_id > end_id:
            agent.messages.append(RuntimeMessage("错误：起始ID不能大于结束ID"))
            return True

        # 检查范围大小，至少10条消息
        range_size = end_id - start_id + 1
        if range_size < 10:
            agent.messages.append(RuntimeMessage("错误：压缩范围至少需要10条消息"))
            return True

        # 检查范围是否有效
        if end_id >= len(agent.messages):
            agent.messages.append(RuntimeMessage("错误：结束ID超出消息范围"))
            return True

        # 收集被删除的用户消息内容
        deleted_user_messages = []
        for msg in agent.messages[start_id : end_id + 1]:
            if isinstance(msg, ChatMessage) and msg.role == "user":
                content = msg.message
                if content:
                    deleted_user_messages.append(content)

        # 直接删除指定范围的消息
        agent.messages[start_id : end_id + 1] = [
            RuntimeMessage(
                f"历史压缩已删除{range_size}条消息（从{start_id}到{end_id}）"
            ),
        ]

        # 如果删除了用户消息，添加额外的消息包含被删除的用户消息内容
        if deleted_user_messages:
            user_messages_summary = "\n".join(
                f"- {msg}" for msg in deleted_user_messages
            )
            agent.messages.insert(
                start_id + 1,
                RuntimeMessage(f"被删除的用户消息内容：\n{user_messages_summary}"),
            )

        agent.messages = [
            msg for msg in agent.messages if not isinstance(msg, CompressRangeRequest)
        ]
    except Exception as exc:
        agent.messages.append(
            RuntimeMessage(f"错误：处理压缩范围时发生异常: {str(exc)}")
        )
    return True
