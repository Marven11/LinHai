"""工具模块主文件。

包含工具消息类和管理器，用于处理工具调用请求和返回结果。
"""

import json
import tempfile
import os
from typing import cast, Any, Callable, Awaitable, Coroutine, Optional
from collections import Counter

from linhai.llm import Message, ToolCallMessage
from linhai.type_hints import LanguageModelMessage
from linhai.tool.base import Tool, global_tools, to_tools_info, ToolSet
from linhai.tool.mcp_connector import MCPConnector
from linhai.config import Config


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
            # 返回文件路径、大小和行数的消息
            message_content = f"内容过长（超过{len(content_str)}字符，共{line_count}行）。已保存到临时文件：{temp_path}。大小：{file_size}字节。请使用sed等工具部分读取。"
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
    def from_json(cls, json_str: str):
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
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        return cls(content=data["content"])


class ToolManager:
    """工具管理器，负责处理工具调用请求"""

    def __init__(self, toolsets: list[ToolSet], config: Optional[Config] = None):
        """初始化工具管理器

        Args:
            config: 可选配置对象
        """
        self.workflows: dict[str, Tool] = {}
        self.config = config
        self.mcp_connector = MCPConnector()

        names = Counter(
            [name for toolset in toolsets for name in toolset.get_tools().keys()]
        )
        if any(count >= 2 for count in names.values()):
            raise ValueError(
                f"Duplicate names: {[name for name, value in names.items() if value >= 2]}"
            )
        self.toolsets = toolsets

    def add_toolset(self, toolset: ToolSet):
        existing_names = set(
            name for toolset in self.toolsets for name in toolset.get_tools().keys()
        )
        duplicate_names = [
            name for name in toolset.get_tools().keys() if name in existing_names
        ]
        if duplicate_names:
            raise ValueError(f"Duplicate names: {duplicate_names}")
        self.toolsets.append(toolset)

    def register_workflow(
        self, name: str, desc: str, func: Callable[[Any], Coroutine[None, None, bool]]
    ):
        self.workflows[name] = Tool(
            name=name, desc=desc, args={}, required=[], func=func
        )

    def get_workflow(self, name: str):
        return self.workflows.get(name)

    def get_tools_info(self) -> list[dict]:
        return [
            info
            for toolset in self.toolsets
            for info in to_tools_info(toolset.get_tools())
        ] + to_tools_info(self.workflows)

    def get_mcp_connector(self):
        return self.mcp_connector

    async def process_tool_call(self, tool_call: ToolCallMessage) -> Message:
        """处理单个工具调用请求并返回结果

        Args:
            tool_call: 工具调用请求对象，包含函数名和参数

        Returns:
            Message: 工具调用结果消息
        """
        args = tool_call.function_arguments if tool_call.function_arguments else {}

        target_toolset = None
        for toolset in self.toolsets:
            if toolset.has_tool(tool_call.function_name):
                target_toolset = toolset
        if target_toolset is None:
            return ToolErrorMessage(f"未找到工具: {tool_call.function_name}")

        try:
            result = target_toolset.call_tool(tool_call.function_name, args)

        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolErrorMessage(content=str(e))

        if isinstance(result, Awaitable):
            result = await result

        # 如果工具返回的是 Message 实例，直接返回
        if isinstance(result, Message):
            return result

        # 否则，用 ToolResultMessage 包装，使用配置的max_output_length或默认值
        max_output_length = 50000
        if (
            self.config
            and self.config.tools
            and self.config.tools.max_output_length is not None
        ):
            max_output_length = self.config.tools.max_output_length

        return ToolResultMessage(content=result, max_output_length=max_output_length)
