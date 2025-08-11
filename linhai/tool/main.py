import json
from typing import cast

from linhai.llm import Message, ToolCallMessage
from linhai.type_hints import LanguageModelMessage
from linhai.tool.base import call_tool


class ToolResultMessage(Message):
    """工具成功结果消息"""

    def __init__(self, content: str):
        self.content = content

    def to_llm_message(self) -> LanguageModelMessage:
        return cast(
            LanguageModelMessage,
            {
                "role": "user",
                "name": "tool-result",
                "content": self.content,
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
        pass

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
            args = (
                json.loads(tool_call.function_arguments)
                if tool_call.function_arguments
                else {}
            )
            result = call_tool(tool_call.function_name, args)
            return ToolResultMessage(
                content=(
                    result
                    if isinstance(result, str)
                    else json.dumps(result, ensure_ascii=False)
                )
            )

        except json.JSONDecodeError as e:
            return ToolErrorMessage(content=f"Invalid arguments JSON: {str(e)}")
        except Exception as e:
            return ToolErrorMessage(content=str(e))
