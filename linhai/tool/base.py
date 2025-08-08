from typing import TypedDict, Callable, Type

type_to_json_repr = {
    "int": "number",
    "float": "number",
    "str": "string",
    "dict": "object",
    "list": "list",
    "bool": "bool",
    "None": "null",
}


class ToolArgInfo(TypedDict):

    desc: str
    type: Type[int | float | str | dict | list | bool | None]


class Tool(TypedDict):

    name: str
    desc: str
    args: dict[str, ToolArgInfo]
    required: list[str]
    func: Callable


tools: dict[str, Tool] = {}


def register_tool(
    name: str, desc: str, args: dict[str, ToolArgInfo], required_args: list[str]
) -> Callable:
    """注册工具装饰器

    Args:
        name: 工具名称
        desc: 工具描述
        args: 参数信息字典
        required_args: 必填参数列表

    Returns:
        装饰器函数
    """

    def _wraps(f: Callable) -> Callable:
        """实际装饰器

        Args:
            f: 被装饰的工具函数

        Returns:
            装饰后的函数
        """
        tools[name] = {
            "name": name,
            "func": f,
            "desc": desc,
            "args": args,
            "required": required_args,
        }
        return f

    return _wraps


def tool_to_toolinfo(tool: Tool) -> dict:
    """将工具转换为工具信息字典

    Args:
        tool: 工具对象

    Returns:
        工具信息字典
    """
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["desc"],
            "parameters": {
                "type": "object",
                "properties": {
                    name: {
                        "description": info["desc"],
                        "type": type_to_json_repr[info["type"].__name__],
                    }
                    for name, info in tool["args"].items()
                },
                "required": tool["required"],
            },
        },
    }


def call_tool(
    name: str, args: dict[str, int | float | str | dict | list | bool | None]
) -> dict:
    """调用指定工具

    Args:
        name: 工具名称
        args: 工具参数

    Returns:
        工具执行结果
    """
    if name not in tools:
        raise ValueError(f"Tool not found: {name}")
    return tools[name]["func"](**args)


def get_tools_info() -> list[dict]:
    """获取所有工具的信息列表

    Returns:
        工具信息字典列表，格式符合OpenAI工具调用规范
    """
    return [tool_to_toolinfo(tool) for tool in tools.values()]
