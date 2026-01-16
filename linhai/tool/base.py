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


class ToolResultFailed(BaseModel):
    """工具失败结果"""
    content: str


def _handle_long_content(content_str: str, max_output_length: int = 50000) -> str:
    """处理长内容，必要时分块保存到文件，返回处理后的消息内容。"""
    if len(content_str) > max_output_length:
        line_count = content_str.count("\n") + 1
        if line_count > 1000:
            lines = content_str.split("\n")
            file_paths = []
            for i in range(0, len(lines), 800):
                chunk_lines = lines[i : i + 800]
                chunk_content = "\n".join(chunk_lines)
                start_line = i + 1
                end_line = min(i + 800, len(lines))
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=f"_lines_{start_line}-{end_line}.txt",
                    delete=False,
                    encoding="utf-8",
                ) as temp_file:
                    temp_file.write(chunk_content)
                    file_paths.append(temp_file.name)
            file_info = "\n".join([f"- {path}" for path in file_paths])
            message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已按行分块保存到以下临时文件（每800行一个文件）：\n{file_info}"
        else:
            file_paths = []
            for i in range(0, len(content_str), 10000):
                chunk_content = content_str[i : i + 10000]
                start_char = i + 1
                end_char = min(i + 10000, len(content_str))
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=f"_chars_{start_char}-{end_char}.txt",
                    delete=False,
                    encoding="utf-8",
                ) as temp_file:
                    temp_file.write(chunk_content)
                    file_paths.append(temp_file.name)
            file_info = "\n".join([f"- {path}" for path in file_paths])
            message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已按字符分块保存到以下临时文件（每10000字符一个文件）：\n{file_info}"
        r = reprlib.Repr()
        r.maxstring = 500
        preview = r.repr(content_str)
        message_content += f"\n\n预览: {preview}"
    else:
        message_content = content_str
    return message_content


class ToolCallResultMessage(Message):
    """工具调用结果消息，包装ToolResultSuccess或ToolResultFailed"""

    def __init__(
        self,
        tool_name: str,
        tool_index: int,
        result: ToolResultSuccess | ToolResultFailed,
        toolcall_argument_repr: str | None = None,
        max_output_length: int = 50000,
    ):
        self.tool_name = tool_name
        self.tool_index = tool_index
        self.result = result
        self.toolcall_argument_repr = toolcall_argument_repr
        self.max_output_length = max_output_length
        
        # 使用辅助函数处理内容
        content_str = result.content
        self.content = _handle_long_content(content_str, max_output_length)

    def to_llm_message(self) -> LanguageModelMessage:
        # 根据result类型决定消息内容
        if isinstance(self.result, ToolResultSuccess):
            status = "工具执行成功"
            data_or_error = f"<<data>>{self.content}<<data>>"
        else:
            status = "工具执行失败" 
            data_or_error = f"<<error>>{self.content}<<error>>"
        
        # 构建消息内容
        content_parts = [
            f"<<tool>>",
            f"<<name>>{self.tool_name}<<name>>",
            f"<<index>>{self.tool_index}<<index>>",
        ]
        # 只有在失败时才包含toolcall_argument_repr
        if isinstance(self.result, ToolResultFailed) and self.toolcall_argument_repr is not None:
            content_parts.append(f"<<toolcall_argument>>{self.toolcall_argument_repr}<<toolcall_argument>>")
        content_parts.extend([
            f"<<message>>{status}<<message>>",
            data_or_error,
            f"<<tool>>",
        ])
        content = "\n".join(content_parts)
        return cast(
            LanguageModelMessage,
            {"role": "user", "content": content},
        )

    def to_json(self) -> str:
        data = {
            "tool_name": self.tool_name,
            "tool_index": self.tool_index,
            "result": {
                "type": "success" if isinstance(self.result, ToolResultSuccess) else "failed",
                "content": self.result.content,
            },
            "toolcall_argument_repr": self.toolcall_argument_repr,
            "content": self.content,
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
            toolcall_argument_repr=data.get("toolcall_argument_repr"),
        )






global_tools = ToolSet()
