"""工具基础模块。

包含工具定义、注册和调用相关的基类和函数。
"""

from typing import TypedDict, Callable, Any, cast, Self  # pylint: disable=unused-import

import json
import tempfile
import reprlib

from pydantic import BaseModel

from linhai.type_hints import LanguageModelMessage
from linhai.llm import Message
import linhai


class ToolArgInfo(TypedDict):
    """工具参数信息"""

    desc: str
    type: str | dict[str, Any]


class Tool(TypedDict):
    """工具定义"""

    name: str
    desc: str
    args: dict[str, ToolArgInfo]
    required: list[str]
    func: Callable
    conflict_with: list[str]


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
        conflict_with: list[str] | None = None,
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
                "conflict_with": conflict_with or [],
            }
            return f

        return _wraps

    def get_tool(self, name: str) -> Callable:
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name]["func"]

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """调用指定工具

        Args:
            name: 工具名称
            args: 工具参数

        Returns:
            工具执行结果
        """
        return self.get_tool(name)(**args)

    def get_tools(self):
        return self.tools

    def has_tool(self, name: str):
        return name in self.tools

    def add_toolset(self, toolset: "ToolSet") -> None:
        """将另一个ToolSet中的所有工具添加到当前ToolSet中。"""
        for tool_name, tool in toolset.tools.items():
            if tool_name in self.tools:
                raise ValueError(f"Tool {tool_name} already exists in this ToolSet")
            self.tools[tool_name] = tool


class ToolResultSuccess(BaseModel):
    """工具成功结果"""

    content: str

    def to_json(self) -> str:
        return self.model_dump_json()


class ToolResultFailed(BaseModel):
    """工具失败结果"""

    content: str

    def to_json(self) -> str:
        return self.model_dump_json()


class ToolCallResultMessage(Message):
    """工具调用结果消息，包装ToolResultSuccess或ToolResultFailed"""

    def __init__(
        self,
        tool_name: str,
        tool_index: int,
        result: ToolResultSuccess | ToolResultFailed,
        toolcall_arguments: dict,
    ):
        self.tool_name = tool_name
        self.tool_index = tool_index
        self.result = result
        self.toolcall_arguments = toolcall_arguments

    def to_llm_message(self) -> LanguageModelMessage:
        return cast(
            LanguageModelMessage,
            {"role": "user", "content": self.get_content()},
        )

    def get_content(self) -> str:
        if isinstance(self.result, ToolResultSuccess):
            status = "工具执行成功"
            data_or_error = f"<<data>>{self.result.content}<<data>>"
        else:
            status = (
                "错误：工具执行失败，你需要缓慢且仔细地反思并总结："
                "1. 失败的原因 2. 用户的需求 3. 你弄错了什么 4. 如何正确完成用户的需求 5. 如何避免工具失败"
            )
            data_or_error = f"<<error>>{self.result.content}<<error>>"

        content_parts = [
            f"<<tool>>",
            f"<<name>>{self.tool_name}<<name>>",
            f"<<index>>{self.tool_index}<<index>>",
        ]
        if isinstance(self.result, ToolResultFailed) and self.toolcall_arguments:
            r = reprlib.Repr()
            r.maxstring = 100
            argument_repr = r.repr(self.toolcall_arguments)
            content_parts.append(
                f"<<toolcall_argument>>{argument_repr}<<toolcall_argument>>"
            )
        content_parts.extend(
            [
                f"<<message>>{status}<<message>>",
                data_or_error,
                "<<tool>>",
            ]
        )
        return "\n".join(content_parts)

    def to_json(self) -> str:
        data = {
            "tool_name": self.tool_name,
            "tool_index": self.tool_index,
            "result": {
                "type": (
                    "success"
                    if isinstance(self.result, ToolResultSuccess)
                    else "failed"
                ),
                "content": self.result.content,
            },
            "toolcall_arguments": self.toolcall_arguments,
            "content": self.result.content,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        data = json.loads(json_str)
        if data["result"]["type"] == "success":
            result = ToolResultSuccess(content=data["result"]["content"])
        else:
            result = ToolResultFailed(content=data["result"]["content"])
        return cls(
            tool_name=data["tool_name"],
            tool_index=data["tool_index"],
            result=result,
            toolcall_arguments=data.get("toolcall_arguments", {}),
        )


global_tools = ToolSet()
