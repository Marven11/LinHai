"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

import json
import tempfile
import os
from typing import cast, Any, Callable, Awaitable, Coroutine

from linhai.llm import Message, ToolCallMessage
from linhai.type_hints import LanguageModelMessage
from linhai.tool.base import call_tool, Tool, get_tools_info, global_tools


class ToolResultMessage(Message):
    """工具成功结果消息"""

    def __init__(self, content: Any):
        # 在内部处理转换逻辑
        if isinstance(content, str):
            content_str = content
        else:
            try:
                content_str = json.dumps(content, ensure_ascii=False)
            except (TypeError, ValueError):
                content_str = str(content)

        # 检查内容长度是否超过50000字符
        if len(content_str) > 50000:
            # 创建临时文件保存内容
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as temp_file:
                temp_file.write(content_str)
                temp_path = temp_file.name
                file_size = os.path.getsize(temp_path)  # 获取文件大小
            # 返回文件路径和大小的消息
            message_content = f"内容过长（超过{len(content_str)}字符）。已保存到临时文件：{temp_path}。大小：{file_size}字节。请使用sed等工具部分读取。"
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
        import json
        return json.dumps(self.to_llm_message())

    @classmethod
    def from_json(cls, json_str: str):
        import json
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
        import json
        return json.dumps(self.to_llm_message())

    @classmethod
    def from_json(cls, json_str: str):
        import json
        data = json.loads(json_str)
        return cls(content=data["content"])


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(self):
        """初始化工具管理器"""
        self.workflows: dict[str, Tool] = {}

    def register_workflow(
        self, name: str, desc: str, func: Callable[[Any], Coroutine[None, None, bool]]
    ):
        self.workflows[name] = Tool(
            name=name, desc=desc, args={}, required=[], func=func
        )

    def get_workflow(self, name: str):
        return self.workflows.get(name)

    def get_tools_info(self) -> list[dict]:
        tools = {**global_tools, **self.workflows}
        return get_tools_info(tools)

    async def process_tool_call(self, tool_call: ToolCallMessage) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        if not tool_call.function_name:
            return ToolErrorMessage(content="Invalid tool call: missing function name")

        try:
            # function_arguments 现在直接是字典，无需解析
            args = tool_call.function_arguments if tool_call.function_arguments else {}
            result = call_tool(tool_call.function_name, args)
            if isinstance(result, Awaitable):
                result = await result

            # 如果工具返回的是 Message 实例，直接返回
            if isinstance(result, Message):
                return result

            # 否则，用 ToolResultMessage 包装
            return ToolResultMessage(content=result)

        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolErrorMessage(content=str(e))
