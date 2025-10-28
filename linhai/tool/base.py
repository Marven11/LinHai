"""工具基础模块。

包含工具定义、注册和调用相关的基类和函数。
"""

from typing import TypedDict, Callable, Any, cast, Self

import json
import tempfile
import os
import reprlib

from linhai.type_hints import LanguageModelMessage
from linhai.llm import Message
import linhai


class ToolArgInfo(TypedDict):
    """工具参数信息"""

    desc: str  # 参数描述
    type: str | dict[str, Any]  # 参数类型字符串或者JSON Schema


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
                "type": arg_info["type"],
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


class ToolResultMessage(Message):
    """工具成功结果消息"""

    def __init__(self, content: Any, max_output_length: int = 50000):
        # 在内部处理转换逻辑
        if isinstance(content, str):
            content_str = content
        else:
            try:
                content_str = json.dumps(content, ensure_ascii=False)
            except (TypeError, ValueError):
                content_str = str(content)

        # 检查内容长度是否超过max_output_length字符
        if len(content_str) > max_output_length:
            # 创建临时文件保存内容
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as temp_file:
                temp_file.write(content_str)
                temp_path = temp_file.name
                file_size = os.path.getsize(temp_path)  # 获取文件大小
            # 计算行数
            line_count = content_str.count("\n") + 1
            # 生成内容预览
            r = reprlib.Repr()
            r.maxstring = 500
            preview = r.repr(content_str)
            # 返回文件路径、大小、行数和预览的消息
            message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已保存到临时文件：{temp_path}。大小：{file_size}字节。请使用sed等工具部分读取。\n预览: {preview}"
            # 我们指导agent使用合适的大小分块读取，避免每次只读100行
            limit = max_output_length / len(content_str)
            if limit > 0.5:
                limit = 0.5
            message_content += f"尝试分块读取：为了提高阅读速度，完整地读取文件，你应该 一次性读取接近{limit*100:.2f}%或者{int(limit*line_count)//10*10}行，如果还是不行就砍半"
        else:
            message_content = content_str

        self.content = message_content

    def to_llm_message(self) -> LanguageModelMessage:

        return cast(
            LanguageModelMessage,
            {
                "role": "user",
                "name": "tool-result",
                "content": self.content,
            },
        )

    def to_json(self) -> str:
        return json.dumps(self.to_llm_message())

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        data = json.loads(json_str)
        return cls(content=data["content"])


class ToolErrorMessage(Message):
    """工具错误消息"""

    def __init__(self, content: str):
        self.content = content

    def to_llm_message(self) -> LanguageModelMessage:
        return cast(
            LanguageModelMessage,
            {
                "role": "user",
                "name": "tool-error",
                "content": self.content,
            },
        )

    def to_json(self) -> str:
        return json.dumps(self.to_llm_message())

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        data = json.loads(json_str)
        return cls(content=data["content"])


global_tools = ToolSet()
