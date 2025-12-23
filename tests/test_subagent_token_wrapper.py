"""测试_handle_subagent_token_wrapper的逻辑。"""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from linhai.cli.app import CLIApp
from linhai.cli.components import MessageWidget, ReasoningContentWidget
from linhai.subagent.message_wrapper import (
    SubAgentAnswerTokenWrapper,
    SubAgentAnswerCompleteWrapper,
)
from linhai.llm import AnswerToken


class TestSubAgentTokenWrapper(unittest.IsolatedAsyncioTestCase):
    """测试_handle_subagent_token_wrapper方法。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = MagicMock()
        self.cli_config = MagicMock()
        self.cli_config.use_nerd_font = False
        self.app = CLIApp(self.group_chat, self.cli_config)
        
        # 模拟必要的组件
        self.app.subagent_current_messages = {}
        self.app.query_one = MagicMock(return_value=MagicMock())
        
        # 模拟subagent容器
        self.subagent_container = MagicMock()
        self.app.query_one.return_value = self.subagent_container
        
        # 模拟_create_subagent_message_widget方法，避免创建真实widget
        self.app._create_subagent_message_widget = MagicMock()
        
        # 模拟_ensure_widget_exists方法，避免isinstance检查问题
        self.app._ensure_widget_exists = MagicMock()
        
    async def test_first_token_reasoning_content_space_then_non_space(self):
        """测试第一个token.reasoning_content是空格，后续token.reasoning_content不是空格。"""
        # 重置mock，因为可能在其他测试中被调用过
        self.app._ensure_widget_exists.reset_mock()
        
        # 第一个token：reasoning_content是空格
        token1 = AnswerToken(
            reasoning_content=" ",  # 空格
            content="",
            token_usage=None
        )
        wrapper1 = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=token1
        )
        
        # 调用_handle_subagent_token_wrapper
        await self.app._handle_subagent_token_wrapper(wrapper1)
        
        # _extract_token_content_and_type 应该返回 ('content', "")，因为空格strip后为空
        # 所以 content 为空，直接返回，不会调用_ensure_widget_exists
        self.app._ensure_widget_exists.assert_not_called()
        
        # 第二个token：reasoning_content不是空格
        token2 = AnswerToken(
            reasoning_content="思考内容",
            content="",
            token_usage=None
        )
        wrapper2 = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=token2
        )
        
        # 调用_handle_subagent_token_wrapper
        await self.app._handle_subagent_token_wrapper(wrapper2)
        
        # 应该调用了_ensure_widget_exists，参数为reasoning类型
        self.app._ensure_widget_exists.assert_called_once()
        args, kwargs = self.app._ensure_widget_exists.call_args
        self.assertEqual(args[0], "test-agent")  # subagent_name
        self.assertEqual(args[1], "思考内容")  # content
        self.assertEqual(args[2], "reasoning")  # token_type
        self.assertEqual(args[3], self.subagent_container)  # subagent_container
        
    async def test_subagent_thinking_then_answer_with_tool_call(self):
        """测试subagent思考后输出回答并调用工具。"""
        # 重置mock
        self.app._ensure_widget_exists.reset_mock()
        
        # 第一阶段：思考阶段，收到多个reasoning token
        thinking_tokens = [
            AnswerToken(reasoning_content="思考1", content="", token_usage=None),
            AnswerToken(reasoning_content="思考2", content="", token_usage=None),
        ]
        
        for token in thinking_tokens:
            wrapper = SubAgentAnswerTokenWrapper(
                subagent_name="test-agent",
                token=token
            )
            await self.app._handle_subagent_token_wrapper(wrapper)
        
        # 验证_ensure_widget_exists被调用了两次，参数正确
        self.assertEqual(self.app._ensure_widget_exists.call_count, 2)
        
        # 检查第一次调用
        call1 = self.app._ensure_widget_exists.call_args_list[0]
        self.assertEqual(call1[0][0], "test-agent")  # subagent_name
        self.assertEqual(call1[0][1], "思考1")  # content
        self.assertEqual(call1[0][2], "reasoning")  # token_type
        self.assertEqual(call1[0][3], self.subagent_container)  # subagent_container
        
        # 检查第二次调用
        call2 = self.app._ensure_widget_exists.call_args_list[1]
        self.assertEqual(call2[0][0], "test-agent")
        self.assertEqual(call2[0][1], "思考2")
        self.assertEqual(call2[0][2], "reasoning")
        self.assertEqual(call2[0][3], self.subagent_container)
        
        # 第二阶段：回答阶段，收到多个content token（包含工具调用）
        answer_tokens = [
            AnswerToken(reasoning_content=None, content="回答第一部分", token_usage=None),
            AnswerToken(reasoning_content=None, content="回答第二部分", token_usage=None),
            AnswerToken(reasoning_content=None, content="```json toolcall\n{\"name\": \"test_tool\", \"arguments\": {}}\n```", token_usage=None),
        ]
        
        for token in answer_tokens:
            wrapper = SubAgentAnswerTokenWrapper(
                subagent_name="test-agent",
                token=token
            )
            await self.app._handle_subagent_token_wrapper(wrapper)
        
        # 总调用次数应为5次（2次thinking + 3次answer）
        self.assertEqual(self.app._ensure_widget_exists.call_count, 5)
        
        # 检查后三次调用为content类型
        for i in range(2, 5):
            call = self.app._ensure_widget_exists.call_args_list[i]
            self.assertEqual(call[0][2], "content")  # token_type应为content

        
    async def test_subagent_thinking_then_answer_without_tool_call(self):
        """测试subagent只思考并回答，没有工具调用。"""
        # 重置mock
        self.app._ensure_widget_exists.reset_mock()
        
        # 第一阶段：思考阶段
        thinking_token = AnswerToken(
            reasoning_content="思考内容",
            content="",
            token_usage=None
        )
        wrapper1 = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=thinking_token
        )
        await self.app._handle_subagent_token_wrapper(wrapper1)
        
        # 验证_ensure_widget_exists被调用一次，参数为reasoning类型
        self.assertEqual(self.app._ensure_widget_exists.call_count, 1)
        call1 = self.app._ensure_widget_exists.call_args_list[0]
        self.assertEqual(call1[0][0], "test-agent")  # subagent_name
        self.assertEqual(call1[0][1], "思考内容")  # content
        self.assertEqual(call1[0][2], "reasoning")  # token_type
        self.assertEqual(call1[0][3], self.subagent_container)  # subagent_container
        
        # 第二阶段：回答阶段，没有工具调用
        answer_token = AnswerToken(
            reasoning_content=None,
            content="回答内容",
            token_usage=None
        )
        wrapper2 = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=answer_token
        )
        await self.app._handle_subagent_token_wrapper(wrapper2)
        
        # 验证_ensure_widget_exists被调用第二次，参数为content类型
        self.assertEqual(self.app._ensure_widget_exists.call_count, 2)
        call2 = self.app._ensure_widget_exists.call_args_list[1]
        self.assertEqual(call2[0][0], "test-agent")  # subagent_name
        self.assertEqual(call2[0][1], "回答内容")  # content
        self.assertEqual(call2[0][2], "content")  # token_type
        self.assertEqual(call2[0][3], self.subagent_container)  # subagent_container
        
    async def test_space_reasoning_content_returns_false(self):
        """测试_extract_token_content_and_type方法对空格reasoning_content的处理。"""
        # 测试空格token
        token = AnswerToken(
            reasoning_content="   ",  # 多个空格
            content="",
            token_usage=None
        )
        
        # 直接调用_extract_token_content_and_type方法
        token_type, content = self.app._extract_token_content_and_type(token)
        
        # reasoning_content是空格，strip后为空，应该返回'content'和空字符串
        self.assertEqual(token_type, 'content')
        self.assertEqual(content, "")
        
        # 测试None reasoning_content
        token2 = AnswerToken(
            reasoning_content=None,
            content="正常内容",
            token_usage=None
        )
        
        token_type2, content2 = self.app._extract_token_content_and_type(token2)
        
        self.assertEqual(token_type2, 'content')
        self.assertEqual(content2, "正常内容")
        
        # 测试非空格reasoning_content
        token3 = AnswerToken(
            reasoning_content="思考内容",
            content="",
            token_usage=None
        )
        
        token_type3, content3 = self.app._extract_token_content_and_type(token3)
        
        self.assertEqual(token_type3, 'reasoning')
        self.assertEqual(content3, "思考内容")


if __name__ == '__main__':
    unittest.main()