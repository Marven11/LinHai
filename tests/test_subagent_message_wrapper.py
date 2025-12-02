"""测试SubAgent消息包装类。"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.subagent.message_wrapper import (
    SubAgentAnswerTokenWrapper,
    SubAgentAnswerCompleteWrapper,
)
from linhai.llm import AnswerToken, AnswerTokenUsage


class TestSubAgentMessageWrapper(unittest.TestCase):
    """测试SubAgent消息包装类。"""
    
    def test_subagent_answer_token_wrapper(self):
        """测试SubAgentAnswerTokenWrapper。"""
        token = AnswerToken(content="test content", reasoning_content="test reasoning")
        wrapper = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=token
        )
        
        self.assertEqual(wrapper.subagent_name, "test-agent")
        self.assertEqual(wrapper.token, token)
        self.assertEqual(wrapper.token.content, "test content")
        self.assertEqual(wrapper.token.reasoning_content, "test reasoning")
        
    def test_subagent_answer_token_wrapper_without_reasoning(self):
        """测试SubAgentAnswerTokenWrapper无推理内容。"""
        token = AnswerToken(content="test content")
        wrapper = SubAgentAnswerTokenWrapper(
            subagent_name="test-agent",
            token=token
        )
        
        self.assertEqual(wrapper.subagent_name, "test-agent")
        self.assertEqual(wrapper.token, token)
        self.assertEqual(wrapper.token.content, "test content")
        self.assertIsNone(wrapper.token.reasoning_content)
        
    def test_subagent_answer_complete_wrapper(self):
        """测试SubAgentAnswerCompleteWrapper。"""
        class MockAnswer:
            def __aiter__(self):
                async def async_gen():
                    yield AnswerToken(content="test")
                return async_gen()
            
            def get_message(self):
                from linhai.llm import AssistantMessage
                return AssistantMessage(message="test")
            
            def get_reasoning_message(self):
                return None
            
            def interrupt(self):
                pass
            
            def truncate(self):
                pass
            
            def get_current_content(self):
                return "test"
            
            def get_token_usage(self):
                return AnswerTokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        
        answer = MockAnswer()
        wrapper = SubAgentAnswerCompleteWrapper(
            subagent_name="test-agent",
            answer=answer
        )
        
        self.assertEqual(wrapper.subagent_name, "test-agent")
        self.assertEqual(wrapper.answer, answer)
        token_usage = wrapper.answer.get_token_usage()
        self.assertIsNotNone(token_usage)
        if token_usage:
            self.assertEqual(token_usage.total_tokens, 150)
        
    def test_dataclass_equality(self):
        """测试数据类相等性。"""
        token1 = AnswerToken(content="content1")
        token2 = AnswerToken(content="content2")
        
        wrapper1 = SubAgentAnswerTokenWrapper("agent1", token1)
        wrapper2 = SubAgentAnswerTokenWrapper("agent1", token1)
        wrapper3 = SubAgentAnswerTokenWrapper("agent2", token1)
        wrapper4 = SubAgentAnswerTokenWrapper("agent1", token2)
        
        self.assertEqual(wrapper1, wrapper2)
        self.assertNotEqual(wrapper1, wrapper3)
        self.assertNotEqual(wrapper1, wrapper4)
        
    def test_dataclass_repr(self):
        """测试数据类表示。"""
        token = AnswerToken(content="test")
        wrapper = SubAgentAnswerTokenWrapper("agent", token)
        
        repr_str = repr(wrapper)
        self.assertIn("SubAgentAnswerTokenWrapper", repr_str)
        self.assertIn("subagent_name='agent'", repr_str)
        

if __name__ == "__main__":
    unittest.main()
