"""测试MessageWidget重构后的功能，使用Textual测试框架。"""

import unittest
import asyncio
from unittest.mock import MagicMock
from textual.app import App
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent import Agent
from linhai.llm import AnswerToken
from linhai.cli.components import (
    ReasoningContentWidget,
    NormalContentWidget,
    ToolCallWidget,
)


class TestMessageWidgetIntegration(unittest.TestCase):
    """使用Textual测试框架测试MessageWidget的完整集成。"""

    def setUp(self):
        """设置测试环境，创建完整的CLI环境。"""

        from linhai.llm import Message
        from linhai.tool.main import ToolManager
        from linhai.tool.mcp_connector import MCPConnector
        from linhai.config import ToolConfig, MCPConfig
        from linhai.tool.base import ToolSet
        from pathlib import Path

        self.group_chat = GroupChat()
        self.cli_config = CLIConfig()

        # CLIApp和Agent会自动注册需要的队列，这里不需要手动注册

        # 创建ToolManager（会自动注册为tool_manager成员）
        ToolManager(
            group_chat=self.group_chat,
            toolsets=[],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("."),
        )

        # 创建MCPConnector（会自动注册为mcp_connector成员）
        MCPConnector(self.group_chat)

        # 创建配置字典
        context = {
            "llms": [MagicMock()],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "system_message": "test",
            "compress_threshold": 0.8,
        }

        # 创建Agent（会自动注册为agent成员）
        # 配置mock对象的get_name方法
        mock_llm = context["llms"][0]
        mock_llm.get_name = MagicMock(return_value="test_llm")

        self.agent = Agent(
            llms=context["llms"],
            compress_threshold=context["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=[],
            llm_name=context["llm_names"][context["current_llm_index"]],
        )

        # 创建CLIApp
        self.app = CLIApp(self.group_chat, self.cli_config)

    async def test_complete_message_flow(self):
        """测试完整的消息流程：用户输入 -> reasoning -> 正常回答 -> 工具调用。"""
        async with self.app.run_test() as pilot:
            # 模拟用户输入
            input_element = self.app.query_one("#input")
            input_element.value = "计算2+2"

            # 触发消息提交
            await self.app._handle_message_submission()
            await pilot.pause()

            container = self.app.query_one("#chat-container")

            # 验证用户消息已添加（第一个widget是欢迎信息，第二个是用户消息）
            self.assertGreaterEqual(len(container.children), 2)

            # 模拟LLM发送多个reasoning token
            await self.group_chat.send(
                "agent_answer",
                AnswerToken(content="", reasoning_content="用户让我计算2+2，"),
            )
            await pilot.pause()

            await self.group_chat.send(
                "agent_answer",
                AnswerToken(content="", reasoning_content="这是一个简单的数学问题，"),
            )
            await pilot.pause()

            await self.group_chat.send(
                "agent_answer",
                AnswerToken(content="", reasoning_content="我应该使用计算器工具。"),
            )
            await pilot.pause()

            # 找到MessageWidget（在欢迎信息和用户消息之后）
            message_widget = None
            for child in container.children:
                if hasattr(child, "current_widget"):
                    message_widget = child
                    break

            self.assertIsNotNone(message_widget)
            # 验证reasoning widget已创建
            self.assertIsInstance(message_widget.current_widget, ReasoningContentWidget)

            # 模拟LLM切换到正常回答
            await self.group_chat.send(
                "agent_answer",
                AnswerToken(content="让我使用计算器", reasoning_content=""),
            )
            await pilot.pause()

            # 验证切换到NormalContentWidget
            self.assertIsInstance(message_widget.current_widget, NormalContentWidget)

            # 模拟LLM发送工具调用
            await self.group_chat.send(
                "agent_answer",
                AnswerToken(
                    content='```json toolcall\n{"name": "safe_calculator", "arguments": {"expression": "2+2"}}\n```\n',
                    reasoning_content="",
                ),
            )
            await pilot.pause()

            # 验证切换到ToolCallWidget
            self.assertIsInstance(message_widget.current_widget, ToolCallWidget)

    async def test_multiple_reasoning_tokens_single_widget(self):
        """测试多个reasoning token只创建一个ReasoningContentWidget。"""
        async with self.app.run_test() as pilot:
            # 模拟用户输入
            input_element = self.app.query_one("#input")
            input_element.value = "思考问题"

            await self.app._handle_message_submission()
            await pilot.pause()

            container = self.app.query_one("#chat-container")

            # 模拟LLM发送多个reasoning token
            message_widget = None
            for i in range(3):
                await self.group_chat.send(
                    "agent_answer",
                    AnswerToken(content="", reasoning_content=f"思考第{i+1}部分"),
                )
                await pilot.pause()

                if message_widget is None:
                    for child in container.children:
                        if hasattr(child, "current_widget"):
                            message_widget = child
                            break

            self.assertIsNotNone(message_widget)
            # 验证只创建了一个ReasoningContentWidget
            self.assertIsInstance(message_widget.current_widget, ReasoningContentWidget)
            # 验证内容已累积
            self.assertIn("思考第1部分", message_widget.current_widget.content_str)
            self.assertIn("思考第2部分", message_widget.current_widget.content_str)
            self.assertIn("思考第3部分", message_widget.current_widget.content_str)

    async def test_multiple_normal_tokens_single_widget(self):
        """测试多个非reasoning token且没有工具调用时只创建一个NormalContentWidget。"""
        async with self.app.run_test() as pilot:
            # 模拟用户输入
            input_element = self.app.query_one("#input")
            input_element.value = "回答问题"

            await self.app._handle_message_submission()
            await pilot.pause()

            container = self.app.query_one("#chat-container")

            # 模拟LLM发送多个normal token
            message_widget = None
            for i in range(3):
                await self.group_chat.send(
                    "agent_answer",
                    AnswerToken(content=f"回答第{i+1}部分", reasoning_content=""),
                )
                await pilot.pause()

                if message_widget is None:
                    for child in container.children:
                        if hasattr(child, "current_widget"):
                            message_widget = child
                            break

            self.assertIsNotNone(message_widget)
            # 验证只创建了一个NormalContentWidget
            self.assertIsInstance(message_widget.current_widget, NormalContentWidget)
            # 验证内容已累积
            self.assertIn("回答第1部分", message_widget.current_widget.content_str)
            self.assertIn("回答第2部分", message_widget.current_widget.content_str)
            self.assertIn("回答第3部分", message_widget.current_widget.content_str)

    async def test_mixed_tokens_widget_switching(self):
        """测试混合token类型时正确切换widget。"""
        async with self.app.run_test() as pilot:
            # 模拟用户输入
            input_element = self.app.query_one("#input")
            input_element.value = "混合测试"

            await self.app._handle_message_submission()
            await pilot.pause()

            container = self.app.query_one("#chat-container")

            # 找到MessageWidget
            message_widget = None
            for child in container.children:
                if hasattr(child, "current_widget"):
                    message_widget = child
                    break

            self.assertIsNotNone(message_widget)

            # 第一阶段：模拟LLM发送reasoning token
            await self.group_chat.send(
                "agent_answer", AnswerToken(content="", reasoning_content="思考内容")
            )
            await pilot.pause()
            reasoning_widget = message_widget.current_widget
            self.assertIsInstance(reasoning_widget, ReasoningContentWidget)

            # 第二阶段：模拟LLM切换到normal token
            await self.group_chat.send(
                "agent_answer",
                AnswerToken(content="现在开始回答", reasoning_content=""),
            )
            await pilot.pause()
            self.assertIsInstance(message_widget.current_widget, NormalContentWidget)
            self.assertNotEqual(message_widget.current_widget, reasoning_widget)

            # 第三阶段：模拟LLM切换到toolcall
            await self.group_chat.send(
                "agent_answer",
                AnswerToken(
                    content='```json toolcall\n{"name": "test_tool", "arguments": {}}\n```\n',
                    reasoning_content="",
                ),
            )
            await pilot.pause()
            self.assertIsInstance(message_widget.current_widget, ToolCallWidget)


if __name__ == "__main__":
    unittest.main()
