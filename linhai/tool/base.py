"""工具基础模块。

包含工具定义、注册和调用相关的基类和函数。
"""

from typing import TypedDict, Callable, Any, cast, Self  # pylint: disable=unused-import

import json
import tempfile
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
    conflict_with: list[str]  # 不能同时调用的工具名称列表


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
            # 计算行数
            line_count = content_str.count("\n") + 1
            
            # 根据行数决定分块策略
            if line_count > 1000:
                # 按行分块：每800行一个文件
                lines = content_str.split('\n')
                file_paths = []
                for i in range(0, len(lines), 800):
                    chunk_lines = lines[i:i+800]
                    chunk_content = '\n'.join(chunk_lines)
                    start_line = i + 1
                    end_line = min(i + 800, len(lines))
                    
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=f"_lines_{start_line}-{end_line}.txt", delete=False, encoding="utf-8"
                    ) as temp_file:
                        temp_file.write(chunk_content)
                        file_paths.append(temp_file.name)
                
                # 生成文件列表信息
                file_info = "\n".join([f"- {path}" for path in file_paths])
                message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已按行分块保存到以下临时文件（每800行一个文件）：\n{file_info}"
            else:
                # 按字符分块：每10000字符一个文件
                file_paths = []
                for i in range(0, len(content_str), 10000):
                    chunk_content = content_str[i:i+10000]
                    start_char = i + 1
                    end_char = min(i + 10000, len(content_str))
                    
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=f"_chars_{start_char}-{end_char}.txt", delete=False, encoding="utf-8"
                    ) as temp_file:
                        temp_file.write(chunk_content)
                        file_paths.append(temp_file.name)
                
                # 生成文件列表信息
                file_info = "\n".join([f"- {path}" for path in file_paths])
                message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已按字符分块保存到以下临时文件（每10000字符一个文件）：\n{file_info}"
            
            # 添加预览信息
            r = reprlib.Repr()
            r.maxstring = 500
            preview = r.repr(content_str)
            message_content += f"\n\n预览: {preview}"
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
