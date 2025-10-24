"""工具基础模块。

包含工具定义、注册和调用相关的基类和函数。
"""

from typing import TypedDict, Callable, Any


class ToolArgInfo(TypedDict):
    """工具参数信息"""

    desc: str  # 参数描述
    type: str  # 参数类型字符串


class Tool(TypedDict):
    """工具定义"""

    name: str  # 工具名称
    desc: str  # 工具描述
    args: dict[str, ToolArgInfo]  # 参数信息
    required: list[str]  # 必填参数列表
    func: Callable  # 工具函数


def to_tools_info(tools: dict[str, Tool]) -> list[dict]:
    """获取所有工具的信息列表

    返回格式符合OpenAI工具调用规范

    Returns:
        工具信息字典列表
    """
    tool_info_list = []
    for tool in tools.values():
        properties: dict[str, Any] = {}
        parameters = {
            "type": "object",
            "properties": properties,
            "required": tool["required"],
        }

        for arg_name, arg_info in tool["args"].items():
            # 直接使用类型字符串作为OpenAI格式的type字段
            properties[arg_name] = {
                "description": arg_info["desc"],
                "type": arg_info["type"],  # 直接使用原始类型字符串
            }

        tool_info = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["desc"],
                "parameters": parameters,
            },
        }
        tool_info_list.append(tool_info)

    return tool_info_list


class ToolSet:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register_tool(
        self,
        name: str,
        desc: str,
        args: dict[str, ToolArgInfo],
        required_args: list[str],
    ):

        def _wraps(f: Callable) -> Callable:
            """实际装饰器

            Args:
                f: 被装饰的工具函数

            Returns:
                装饰后的函数
            """
            self.tools[name] = {
                "name": name,
                "func": f,
                "desc": desc,
                "args": args,
                "required": required_args,
            }
            return f

        return _wraps

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """调用指定工具

        Args:
            name: 工具名称
            args: 工具参数

        Returns:
            工具执行结果
        """
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name]["func"](**args)

    def get_tools(self):
        return self.tools

    def has_tool(self, name: str):
        return name in self.tools


global_tools = ToolSet()
