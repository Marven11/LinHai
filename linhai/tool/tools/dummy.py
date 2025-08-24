from linhai.tool.base import register_tool

# 调用会被agent拦截的，和agent运行流程相关的tool
# 具体见agent.py


@register_tool(
    name="compress_history",
    desc="压缩历史：总结历史消息并删除不重要的消息。"
    "调用这个特殊工具来开始压缩历史的流程。在调用之后会出现一条system prompt."
    "按照出现的system prompt执行流程即可。"
    "不要执行多余的步骤",
    args={},
    required_args=[],
)
def compress_history() -> str:
    return ""


@register_tool(
    name="get_token_usage",
    desc="获取token使用情况。",
    args={},
    required_args=[],
)
def get_token_usage() -> str:
    return ""


@register_tool(
    name="switch_to_cheap_llm",
    desc="切换到廉价LLM模式，指定接下来要使用的消息数量。",
    args={
        "message_count": {
            "desc": "要使用廉价LLM的消息数量",
            "type": "int"
        }
    },
    required_args=["message_count"],
)
def switch_to_cheap_llm(message_count: int) -> str:
    return ""