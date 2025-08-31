"""虚拟工具模块，提供与Agent流程相关的特殊工具函数。

这些工具函数通常由Agent内部处理，不会实际执行外部操作。
"""

from linhai.tool.base import register_tool, ToolArgInfo

# 调用会被agent拦截的，和agent运行流程相关的tool
# 具体见agent.py


@register_tool(
    name="compress_history",
    desc="压缩历史：总结历史消息并删除不重要的消息。"
    "调用这个特殊工具来开始压缩历史的流程。在调用之后会出现一条system prompt."
    "按照出现的system prompt执行流程即可。"
    "不要执行多余的步骤。"
    "优先使用compress_history_range而不是这个工具",
    args={},
    required_args=[],
)
def compress_history() -> str:
    """压缩历史消息工具函数。

    此函数由Agent内部处理，用于触发历史压缩流程。

    Returns:
        str: 空字符串，实际处理由Agent完成。
    """
    return ""


@register_tool(
    name="get_token_usage",
    desc="获取token使用情况。",
    args={},
    required_args=[],
)
def get_token_usage() -> str:
    """获取token使用情况工具函数。

    此函数由Agent内部处理，用于获取当前token用量。

    Returns:
        str: 空字符串，实际处理由Agent完成。
    """
    return ""


@register_tool(
    name="switch_to_cheap_llm",
    desc="切换到廉价LLM模式，指定接下来要使用的消息数量。",
    args={"message_count": ToolArgInfo(desc="要使用廉价LLM的消息数量", type="int")},
    required_args=["message_count"],
)
def switch_to_cheap_llm(message_count: int) -> str:
    """切换到廉价LLM模式工具函数。

    此函数由Agent内部处理，用于切换LLM模式。

    Args:
        message_count: 要使用廉价LLM的消息数量。

    Returns:
        str: 空字符串，实际处理由Agent完成。
    """
    _ = message_count  # 避免未使用参数警告
    return ""


@register_tool(
    name="thanox_history",
    desc="随机删除一半消息（不包括前5条系统消息）。调用这个工具来触发随机删除流程。",
    args={},
    required_args=[],
)
def thanox_history() -> str:
    """随机删除历史消息工具函数。

    此函数由Agent内部处理，用于触发随机删除流程。

    Returns:
        str: 空字符串，实际处理由Agent完成。
    """
    return ""


@register_tool(
    name="compress_history_range",
    desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
    args={},
    required_args=[],
)
def compress_history_range() -> str:
    """压缩指定范围历史消息工具函数。

    此函数由Agent内部处理，用于触发指定范围的历史压缩流程。

    Returns:
        str: 空字符串，实际处理由Agent完成。
    """
    return ""
