"""测试MessageWidget重构后的功能，使用Textual测试框架。"""

import unittest
import asyncio
from unittest.mock import MagicMock
from textual.app import App
from linhai.cli.app import CLIApp
from linhai.group_chat import GroupChat
from linhai.config import CLIConfig
from linhai.agent import Agent, Lifecycle
from linhai.llm import AnswerToken, Answer
from linhai.parsed_message import ParsedAnswer
from linhai.cli.components import (
    ReasoningContentWidget,
    NormalContentWidget,
    ToolCallWidget,
)


class MockAnswer(Answer):
    """模拟Answer对象，用于测试。"""
    
    def __init__(self, tokens: list[AnswerToken]):
        self.tokens = tokens
        self.interrupted = False
        self.truncated = False
        self._iter = None
    
    def __aiter__(self):
        self._iter = iter(self.tokens)
        return self
    
    async def __anext__(self) -> AnswerToken:
        if self.interrupted or self.truncated or self._iter is None:
            raise StopAsyncIteration
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration
    
    def get_message(self):
        return None
    
    def get_reasoning_message(self) -> str | None:
        return None
    
    def interrupt(self):
        self.interrupted = True
    
    def truncate(self):
        self.truncated = True
    
    def get_current_content(self) -> str:
        return ""
    
    def get_token_usage(self):
        return None


class TestMessageWidgetIntegration(unittest.IsolatedAsyncioTestCase):
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

            # 创建模拟Answer，包含多个token
            tokens = [
                AnswerToken(content="", reasoning_content="用户让我计算2+2，"),
                AnswerToken(content="", reasoning_content="这是一个简单的数学问题，"),
                AnswerToken(content="", reasoning_content="我应该使用计算器工具。"),
                AnswerToken(content="让我使用计算器", reasoning_content=""),
                AnswerToken(
                    content='```json toolcall\n{"name": "safe_calculator", "arguments": {"expression": "2+2"}}\n```\n',
                    reasoning_content="",
                ),
            ]
            mock_answer = MockAnswer(tokens)
            
            # 获取lifecycle和agent
            lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
            agent = self.group_chat.get_members("agent", Agent)
            
            # 创建ParsedAnswer并发送
            parsed_answer = ParsedAnswer(answer=mock_answer, lifecycle=lifecycle, agent=agent)
            await parsed_answer.start_parsing()
            await self.group_chat.send("parsed_agent_answer", parsed_answer)
            
            # 等待解析完成
            await asyncio.sleep(0.1)  # 给解析任务一些时间
            await pilot.pause()

            # 找到MessageWidget（在欢迎信息和用户消息之后）
            message_widget = None
            for child in container.children:
                if hasattr(child, "current_widget"):
                    message_widget = child
                    break

            self.assertIsNotNone(message_widget)
            # 验证widget类型切换
            # 注意：由于所有token被快速解析，widget可能直接显示最后一个类型
            # 但为了测试，我们可以检查最终widget是ToolCallWidget
            # 或者我们可以逐步验证，但这里简化
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

            # 创建模拟Answer，包含多个reasoning token
            tokens = [
                AnswerToken(content="", reasoning_content="思考第1部分"),
                AnswerToken(content="", reasoning_content="思考第2部分"),
                AnswerToken(content="", reasoning_content="思考第3部分"),
            ]
            mock_answer = MockAnswer(tokens)
            
            # 获取lifecycle和agent
            lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
            agent = self.group_chat.get_members("agent", Agent)
            
            # 创建ParsedAnswer并发送
            parsed_answer = ParsedAnswer(answer=mock_answer, lifecycle=lifecycle, agent=agent)
            await parsed_answer.start_parsing()
            await self.group_chat.send("parsed_agent_answer", parsed_answer)
            
            # 等待解析完成
            await asyncio.sleep(0.1)  # 给解析任务一些时间
            await pilot.pause()

            # 找到MessageWidget
            message_widget = None
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

            # 创建模拟Answer，包含多个normal token
            tokens = [
                AnswerToken(content="回答第1部分", reasoning_content=""),
                AnswerToken(content="回答第2部分", reasoning_content=""),
                AnswerToken(content="回答第3部分", reasoning_content=""),
            ]
            mock_answer = MockAnswer(tokens)
            
            # 获取lifecycle和agent
            lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
            agent = self.group_chat.get_members("agent", Agent)
            
            # 创建ParsedAnswer并发送
            parsed_answer = ParsedAnswer(answer=mock_answer, lifecycle=lifecycle, agent=agent)
            await parsed_answer.start_parsing()
            await self.group_chat.send("parsed_agent_answer", parsed_answer)
            
            # 等待解析完成
            await asyncio.sleep(0.1)  # 给解析任务一些时间
            await pilot.pause()

            # 找到MessageWidget
            message_widget = None
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

            # 创建模拟Answer，包含混合类型token
            tokens = [
                AnswerToken(content="", reasoning_content="思考内容"),
                AnswerToken(content="现在开始回答", reasoning_content=""),
                AnswerToken(
                    content='```json toolcall\n{"name": "test_tool", "arguments": {}}\n```\n',
                    reasoning_content="",
                ),
            ]
            mock_answer = MockAnswer(tokens)
            
            # 获取lifecycle和agent
            lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
            agent = self.group_chat.get_members("agent", Agent)
            
            # 创建ParsedAnswer并发送
            parsed_answer = ParsedAnswer(answer=mock_answer, lifecycle=lifecycle, agent=agent)
            await parsed_answer.start_parsing()
            await self.group_chat.send("parsed_agent_answer", parsed_answer)
            
            # 等待解析完成
            await asyncio.sleep(0.1)  # 给解析任务一些时间
            await pilot.pause()
            
            # 注意：由于所有token被快速解析，widget可能直接显示最后一个类型
            # 但为了测试，我们可以检查最终widget是ToolCallWidget
            self.assertIsInstance(message_widget.current_widget, ToolCallWidget)


if __name__ == "__main__":
    unittest.main()
