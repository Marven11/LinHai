import asyncio
import json

from linhai.queue import Queue
from linhai.llm import Message, ToolCallMessage
from linhai.type_hints import LanguageModelMessage
from linhai.tool.base import call_tool


class ToolResultMessage(Message):
    """工具成功结果消息"""

    def __init__(self, tool_call_id: str, content: str):
        self.tool_call_id = tool_call_id
        self.content = content

    def to_chat_message(self) -> LanguageModelMessage:
        return {
            "role": "tool",
            "content": self.content,
            "tool_call_id": self.tool_call_id,
        }


class ToolErrorMessage(Message):
    """工具错误消息"""

    def __init__(self, tool_call_id: str, content: str):
        self.tool_call_id = tool_call_id
        self.content = content

    def to_chat_message(self) -> LanguageModelMessage:
        return {
            "role": "tool",
            "content": self.content,
            "tool_call_id": self.tool_call_id,
        }


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(
        self,
        tool_input_queue: Queue[ToolCallMessage],
        tool_output_queue: Queue[Message],
    ):
        """
        初始化工具管理器

        Args:
            tool_input_queue: 接收工具调用请求的队列
            tool_output_queue: 发送工具调用结果的队列
        """
        self.tool_input_queue = tool_input_queue
        self.tool_output_queue = tool_output_queue

    async def process_tool_call(self, tool_call: ToolCallMessage) -> None:
        """处理单个工具调用请求

        Args:
            tool_call: 工具调用请求对象，包含工具调用ID、函数名和参数
        """
        if not tool_call.function_name:
            await self.tool_output_queue.put(
                ToolErrorMessage(tool_call_id=tool_call.id or "", content="Invalid tool call: missing function name")
            )
            return

        try:
            args = json.loads(tool_call.function_arguments) if tool_call.function_arguments else {}
            result = call_tool(tool_call.function_name, args)

            await self.tool_output_queue.put(
                ToolResultMessage(
                    tool_call_id=tool_call.id or "", 
                    content=json.dumps(result, ensure_ascii=False)
                )
            )

        except json.JSONDecodeError as e:
            await self.tool_output_queue.put(
                ToolErrorMessage(tool_call_id=tool_call.id or "", content=f"Invalid arguments JSON: {str(e)}")
            )
        except Exception as e:
            await self.tool_output_queue.put(
                ToolErrorMessage(tool_call_id=tool_call.id or "", content=str(e))
            )

    async def run(self) -> None:
        """启动工具管理器主循环"""
        while True:
            tool_call = await self.tool_input_queue.get()
            await self.process_tool_call(tool_call)


async def start_tool_manager(
    tool_input_queue: Queue, tool_output_queue: Queue
) -> ToolManager:
    """启动工具管理器

    Args:
        tool_input_queue: 接收工具调用请求的队列
        tool_output_queue: 发送工具调用结果的队列

    Returns:
        初始化的ToolManager实例
    """
    manager = ToolManager(tool_input_queue, tool_output_queue)
    asyncio.create_task(manager.run())
    return manager
