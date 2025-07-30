from typing import TypedDict, Callable, Type, cast
from pathlib import Path
import asyncio
import json

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionChunk,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionToolMessageParam,
)
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
import tomllib

type_to_json_repr = {
    "int": "number",
    "float": "number",
    "dict": "object",
    "list": "list",
    "bool": "bool",
    "None": "null",
}


class ToolArgInfo(TypedDict):
    desc: str
    type: Type[int | float | dict | list | bool | None]


class Tool(TypedDict):
    name: str
    desc: str
    args: dict[str, ToolArgInfo]
    required: list[str]
    func: Callable


tools: dict[str, Tool] = {}


def register_tool(
    name: str, desc: str, args: dict[str, ToolArgInfo], required_args: list[str]
):
    def _wraps(f: Callable):
        tools[name] = {
            "name": name,
            "func": f,
            "desc": desc,
            "args": args,
            "required": required_args,
        }
        return f

    return _wraps


def tool_to_toolinfo(tool: Tool):
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["desc"],
            "parameters": {
                "type": "object",
                "properties": {
                    name: {
                        "desc": info["desc"],
                        "type": type_to_json_repr[info["type"].__name__],
                    }
                    for name, info in tool["args"].items()
                },
                "required": tool["required"],
            },
        },
    }


@register_tool(
    name="add_two_numbers",
    desc="将两个数字a与b相加",
    args={
        "a": ToolArgInfo(desc="第一个数字a", type=float),
        "b": ToolArgInfo(desc="第二个数字b", type=float),
    },
    required_args=["a", "b"],
)
def add_two_numbers(a, b):
    return a + b


def collect_tool_calls(
    tool_call_deltas: list[ChoiceDeltaToolCall], existing_calls: dict[int, dict]
) -> dict[int, dict]:
    """收集流式响应中的工具调用片段

    Args:
        tool_call_deltas: 从API响应中获取的工具调用增量
        existing_calls: 已收集的工具调用映射

    Returns:
        更新后的工具调用映射，包含完整工具调用信息
    """
    for tc in tool_call_deltas:
        if tc.index not in existing_calls:
            existing_calls[tc.index] = {
                "id": "",
                "function": {"name": "", "arguments": ""},
                "type": "function",
            }
        tool_call = existing_calls[tc.index]
        if tc.id:
            tool_call["id"] = tc.id
        if tc.function:
            if tc.function.name:
                tool_call["function"]["name"] += tc.function.name
            if tc.function.arguments:
                tool_call["function"]["arguments"] += tc.function.arguments
    return existing_calls


def call_tool(
    name: str, args: dict[str, int | float | dict | list | bool | None]
) -> dict:
    return tools[name]["func"](**args)


async def main():
    # 读取配置文件
    config_path = Path("config.toml")
    if not config_path.exists():
        print(f"错误：配置文件 {config_path} 不存在")
        print("请创建config.toml并配置OpenAI参数")
        return

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        print(f"读取配置文件失败: {str(e)}")
        return

    # 从配置获取OpenAI参数
    openai_config = config.get("llm", {})

    if "api_key" not in openai_config:
        print("错误：配置文件中未设置API密钥")
        print("请在config.toml的[llm]部分添加api_key")
        return

    # 创建OpenAI客户端
    client = AsyncOpenAI(
        api_key=openai_config["api_key"], base_url=openai_config["base_url"]
    )
    toolinfos = [tool_to_toolinfo(tool) for tool in tools.values()]
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(
            role="system", content="你是一个智能助手，可以使用工具解决问题。"
        ),
        ChatCompletionUserMessageParam(role="user", content="请计算5加7等于多少？"),
    ]

    # 工具调用循环
    while True:
        try:
            # 重置每次请求的变量
            current_content_chunks = []
            tool_calls_map = {}

            # 创建API请求 (使用正确类型)
            tools_param = cast(list[ChatCompletionToolParam], toolinfos)
            response = await client.chat.completions.create(
                model=openai_config["model"],
                messages=messages,
                tools=tools_param,
                tool_choice="auto",
                stream=True,
            )

            # 处理流式响应
            async for chunk in response:
                chunk = cast(ChatCompletionChunk, chunk)
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    # 收集内容块
                    if delta.content:
                        current_content_chunks.append(delta.content)
                        print(delta.content, end="", flush=True)

                    # 收集工具调用
                    if delta.tool_calls:
                        tool_calls_map = collect_tool_calls(
                            delta.tool_calls, tool_calls_map
                        )

            # 处理收集到的工具调用
            tool_calls_list = list(tool_calls_map.values())

            # 如果没有工具调用，保存内容并结束循环
            if not tool_calls_list:
                content_chunks = current_content_chunks
                break

            # 添加助手消息到历史记录（包含工具调用）
            assistant_message = {
                "role": "assistant",
                "content": (
                    "".join(current_content_chunks) if current_content_chunks else None
                ),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                        "type": "function",
                    }
                    for tc in tool_calls_list
                ],
            }
            assistant_message = cast(ChatCompletionMessageParam, assistant_message)
            messages.append(assistant_message)

            # 处理工具调用
            for tool_call in tool_calls_list:
                # 提取工具名称和参数
                tool_name = tool_call["function"]["name"]
                arguments_str = tool_call["function"]["arguments"]
                arguments = {}
                if arguments_str:
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        # 忽略JSON解析错误
                        pass

                # 执行工具调用
                tool_result = call_tool(tool_name, arguments)

                # 将工具结果添加到消息历史
                tool_message: ChatCompletionToolMessageParam = {
                    "role": "tool",
                    "content": json.dumps(tool_result),
                    "tool_call_id": tool_call["id"],
                }
                messages.append(tool_message)

        except Exception:
            import traceback

            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(main())
