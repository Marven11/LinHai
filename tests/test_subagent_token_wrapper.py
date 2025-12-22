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
        
    async def test_first_token_reasoning_content_space_then_non_space(self):
        """测试第一个token.reasoning_content是空格，后续token.reasoning_content不是空格。"""
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
        # 所以 content 为空，直接返回，不会创建widget
        self.assertEqual(len(self.app.subagent_current_messages), 0)
        
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
        
        # 模拟ReasoningContentWidget的创建
        with patch('linhai.cli.app.ReasoningContentWidget', autospec=True) as mock_reasoning_widget_class:
            mock_widget = MagicMock(spec=ReasoningContentWidget)
            mock_widget.append_content = MagicMock()
            mock_widget.update_display = MagicMock()
            mock_widget.finish_streaming = MagicMock()
            mock_reasoning_widget_class.return_value = mock_widget
            
            await self.app._handle_subagent_token_wrapper(wrapper2)
            
            # 应该创建了widget
            mock_reasoning_widget_class.assert_called_once_with(
                role="assistant",
                content="思考内容",
                sender_name="test-agent",
            )
            self.assertEqual(len(self.app.subagent_current_messages), 1)
            self.assertIn("test-agent", self.app.subagent_current_messages)
            self.subagent_container.mount.assert_called_once_with(mock_widget)
            mock_widget.update_display.assert_called_once()
        
    async def test_subagent_thinking_then_answer_with_tool_call(self):
        """测试subagent思考后输出回答并调用工具。"""
        # 第一阶段：思考阶段，收到多个reasoning token
        thinking_tokens = [
            AnswerToken(reasoning_content="思考1", content="", token_usage=None),
            AnswerToken(reasoning_content="思考2", content="", token_usage=None),
        ]
        
        # 模拟ReasoningContentWidget的创建
        with patch('linhai.cli.app.ReasoningContentWidget', autospec=True) as mock_reasoning_widget_class:
            reasoning_widget = MagicMock(spec=ReasoningContentWidget)
            reasoning_widget.append_content = MagicMock()
            reasoning_widget.update_display = MagicMock()
            reasoning_widget.finish_streaming = MagicMock()
            mock_reasoning_widget_class.return_value = reasoning_widget
            
            for token in thinking_tokens:
                wrapper = SubAgentAnswerTokenWrapper(
                    subagent_name="test-agent",
                    token=token
                )
                await self.app._handle_subagent_token_wrapper(wrapper)
            
            # 检查：应该创建了一个ReasoningContentWidget
            mock_reasoning_widget_class.assert_called_once_with(
                role="assistant",
                content="思考1",
                sender_name="test-agent",
            )
            self.assertEqual(len(self.app.subagent_current_messages), 1)
            self.assertIs(self.app.subagent_current_messages["test-agent"], reasoning_widget)
            # 第二个token应该调用了append_content
            reasoning_widget.append_content.assert_called_once_with("思考2")
        
        # 第二阶段：回答阶段，收到多个content token（包含工具调用）
        # 模拟MessageWidget的创建
        with patch('linhai.cli.app.MessageWidget', autospec=True) as mock_message_widget_class:
            message_widget = MagicMock(spec=MessageWidget)
            message_widget.append_content = MagicMock()
            message_widget.update_display = MagicMock()
            mock_message_widget_class.return_value = message_widget
            
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
            
            # 检查：应该创建了一个MessageWidget
            mock_message_widget_class.assert_called_once_with(
                role="assistant",
                content="",
                sender_name="test-agent",
            )
            # widget应该被添加到当前消息中，但注意类型变化时，旧widget被移除
            self.assertEqual(len(self.app.subagent_current_messages), 1)
            self.assertIs(self.app.subagent_current_messages["test-agent"], message_widget)
            # MessageWidget应该收到了三个append_content调用（所有answer tokens）
            self.assertEqual(message_widget.append_content.call_count, 3)
            message_widget.append_content.assert_any_call("回答第一部分")
            message_widget.append_content.assert_any_call("回答第二部分")
            message_widget.append_content.assert_any_call("```json toolcall\n{\"name\": \"test_tool\", \"arguments\": {}}\n```")
        
    async def test_subagent_thinking_then_answer_without_tool_call(self):
        """测试subagent只思考并回答，没有工具调用。"""
        # 第一阶段：思考阶段
        thinking_token = AnswerToken(
            reasoning_content="思考内容",
            content="",
            token_usage=None
        )
        
        # 模拟ReasoningContentWidget的创建
        with patch('linhai.cli.app.ReasoningContentWidget', autospec=True) as mock_reasoning_widget_class:
            reasoning_widget = MagicMock(spec=ReasoningContentWidget)
            reasoning_widget.append_content = MagicMock()
            reasoning_widget.update_display = MagicMock()
            reasoning_widget.finish_streaming = MagicMock()
            mock_reasoning_widget_class.return_value = reasoning_widget
            
            wrapper1 = SubAgentAnswerTokenWrapper(
                subagent_name="test-agent",
                token=thinking_token
            )
            await self.app._handle_subagent_token_wrapper(wrapper1)
            
            # 检查：创建了ReasoningContentWidget
            mock_reasoning_widget_class.assert_called_once_with(
                role="assistant",
                content="思考内容",
                sender_name="test-agent",
            )
            self.assertEqual(len(self.app.subagent_current_messages), 1)
            self.assertIs(self.app.subagent_current_messages["test-agent"], reasoning_widget)
            reasoning_widget.update_display.assert_called_once()
        
        # 第二阶段：回答阶段，没有工具调用
        # 模拟MessageWidget的创建，注意：由于类型变化，之前的widget会从字典中移除，但容器中可能还有
        with patch('linhai.cli.app.MessageWidget', autospec=True) as mock_message_widget_class:
            message_widget = MagicMock(spec=MessageWidget)
            message_widget.append_content = MagicMock()
            message_widget.update_display = MagicMock()
            mock_message_widget_class.return_value = message_widget
            
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
            
            # 检查：创建了MessageWidget
            mock_message_widget_class.assert_called_once_with(
                role="assistant",
                content="回答内容",
                sender_name="test-agent",
            )
            # 由于类型变化，当前消息字典中应该更新为MessageWidget
            self.assertEqual(len(self.app.subagent_current_messages), 1)
            self.assertIs(self.app.subagent_current_messages["test-agent"], message_widget)
            message_widget.update_display.assert_called_once()
        
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