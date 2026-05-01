"""工具基础模块。

包含工具定义、注册和调用相关的基类和函数。
"""

from typing import (
    TypedDict,
    Callable,
    Any,
    Awaitable,
    Protocol,
    runtime_checkable,
)

import json
import tempfile
import reprlib

from pydantic import BaseModel

from linhai.type_hints import (
    LanguageModelMessage,
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam,
)
from linhai.base import Message
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
    func: Callable[..., "ToolResult | Awaitable[ToolResult]"]


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
    ):

        def _wraps(
            f: Callable[..., "ToolResult | Awaitable[ToolResult]"],
        ) -> Callable[..., "ToolResult | Awaitable[ToolResult]"]:
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

    def get_tool(
        self, name: str
    ) -> Callable[..., "ToolResult | Awaitable[ToolResult]"]:
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


ToolResultContent = (
    str | list[ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam]
)


@runtime_checkable
class ToolResult(Protocol):
    """工具结果协议，定义工具返回值的接口。"""

    def to_llm_content(self) -> ToolResultContent:
        """转换为应插入LLM消息content字段的内容。"""
        raise NotImplementedError()


class SuccessfulToolResult(BaseModel):
    """工具成功结果"""

    content: str

    def to_llm_content(self) -> str:
        return self.content

    def to_json(self) -> str:
        return self.model_dump_json()


class FailedToolResult(BaseModel):
    """工具失败结果"""

    content: str

    def to_llm_content(self) -> str:
        return self.content

    def to_json(self) -> str:
        return self.model_dump_json()


class ToolCallResultMessage(Message):
    """工具调用结果消息，包装ToolResult"""

    def __init__(
        self,
        tool_name: str,
        tool_index: int,
        result: ToolResult,
        toolcall_arguments: dict,
    ):
        self.tool_name = tool_name
        self.tool_index = tool_index
        self.result = result
        self.toolcall_arguments = toolcall_arguments

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": self.get_content()}

    def get_content(self) -> str:
        if isinstance(self.result, FailedToolResult):
            status = (
                "错误：工具执行失败，你需要缓慢且仔细地反思并总结："
                "1. 失败的原因 2. 用户的需求 3. 你弄错了什么 4. 如何正确完成用户的需求 5. 如何避免工具失败"
            )
        else:
            status = "工具执行成功"

        content_parts = [
            "<<tool>>",
            f"<<name>>{self.tool_name}<<name>>",
            f"<<index>>{self.tool_index}<<index>>",
        ]
        if isinstance(self.result, FailedToolResult) and self.toolcall_arguments:
            r = reprlib.Repr()
            r.maxstring = 100
            argument_repr = r.repr(self.toolcall_arguments)
            content_parts.append(
                f"<<toolcall_argument>>{argument_repr}<<toolcall_argument>>"
            )
        llm_content = self.result.to_llm_content()
        content_str = llm_content if isinstance(llm_content, str) else str(llm_content)
        if isinstance(self.result, FailedToolResult):
            data_or_error = f"<<error>>{content_str}<<error>>"
        else:
            data_or_error = f"<<data>>{content_str}<<data>>"
        content_parts.extend(
            [
                f"<<message>>{status}<<message>>",
                data_or_error,
                "<<tool>>",
            ]
        )
        return "\n".join(content_parts)

    def to_json(self) -> str:
        content = (
            self.result.content
            if isinstance(self.result, (SuccessfulToolResult, FailedToolResult))
            else str(self.result.to_llm_content())
        )
        data = {
            "tool_name": self.tool_name,
            "tool_index": self.tool_index,
            "result": {
                "type": (
                    "failed" if isinstance(self.result, FailedToolResult) else "success"
                ),
                "content": content,
            },
            "toolcall_arguments": self.toolcall_arguments,
            "content": content,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        if data["result"]["type"] == "success":
            result = SuccessfulToolResult(content=data["result"]["content"])
        else:
            result = FailedToolResult(content=data["result"]["content"])
        return cls(
            tool_name=data["tool_name"],
            tool_index=data["tool_index"],
            result=result,
            toolcall_arguments=data.get("toolcall_arguments", {}),
        )


utils_tools = ToolSet()
