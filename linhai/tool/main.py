"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

import json
from typing import cast, Any

from linhai.llm import Message, ToolCallMessage
from linhai.type_hints import LanguageModelMessage
from linhai.tool.base import call_tool


class ToolResultMessage(Message):
    """工具成功结果消息"""

    def __init__(self, content: Any):
        self.content = content

    def to_llm_message(self) -> LanguageModelMessage:
        # 在内部处理转换逻辑
        if isinstance(self.content, str):
            content_str = self.content
        else:
            try:
                content_str = json.dumps(self.content, ensure_ascii=False)
            except (TypeError, ValueError):
                content_str = str(self.content)

        return cast(
            LanguageModelMessage,
            {
                "role": "user",
                "name": "tool-result",
                "content": content_str,
            },
        )


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


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(self):
        """初始化工具管理器"""

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

            # 如果工具返回的是 Message 实例，直接返回
            if isinstance(result, Message):
                return result

            # 否则，用 ToolResultMessage 包装
            return ToolResultMessage(content=result)

        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolErrorMessage(content=str(e))
