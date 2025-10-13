"""LLM模块的单元测试"""

import unittest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

# 导入要测试的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from linhai.llm import OpenAiAnswer, OpenAi, SystemMessage, ChatMessage


class TestOpenAiAnswer(unittest.TestCase):
    """OpenAiAnswer测试类"""

    def setUp(self):
        """测试前准备"""
        # 创建一个模拟的stream对象
        self.mock_stream = AsyncMock()
        self.answer = OpenAiAnswer(self.mock_stream)

    def test_get_token_usage_returns_none_when_no_tokens(self):
        """测试当没有token使用时返回None"""
        # 设置total_tokens为0
        self.answer.total_tokens = 0
        result = self.answer.get_token_usage()
        self.assertIsNone(result)

    def test_get_token_usage_returns_correct_dict(self):
        """测试get_token_usage返回正确的字典"""
        # 设置token计数
        self.answer.input_tokens = 100
        self.answer.output_tokens = 50
        self.answer.total_tokens = 150
        
        result = self.answer.get_token_usage()
        
        expected = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150
        }
        self.assertEqual(result, expected)

    def test_token_count_initialization(self):
        """测试token计数正确初始化"""
        self.assertEqual(self.answer.input_tokens, 0)
        self.assertEqual(self.answer.output_tokens, 0)
        self.assertEqual(self.answer.total_tokens, 0)


class TestOpenAi(unittest.IsolatedAsyncioTestCase):
    """OpenAi测试类"""

    def setUp(self):
        """测试前准备"""
        self.openai = OpenAi(
            api_key="test_key",
            base_url="https://api.example.com",
            model="test-model",
            openai_config={},
            chat_completion_kwargs={}
        )

    async def test_answer_stream_returns_answer_instance(self):
        """测试answer_stream返回Answer实例"""
        # 创建模拟的OpenAI客户端和响应
        mock_client = AsyncMock()
        mock_stream = AsyncMock()
        
        # 设置模拟的流式响应
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta = MagicMock()
        mock_chunk.choices[0].delta.content = "Hello"
        mock_chunk.usage = None
        
        # 模拟异步迭代
        async def async_iter():
            yield mock_chunk
        
        mock_stream.__aiter__.return_value = async_iter()
        mock_client.chat.completions.create.return_value = mock_stream
        self.openai.openai = mock_client
        
        # 测试消息历史
        history = [SystemMessage("You are a helpful assistant")]
        
        # 调用方法
        answer = await self.openai.answer_stream(history)
        
        # 验证返回的是Answer实例
        self.assertIsInstance(answer, OpenAiAnswer)


if __name__ == "__main__":
    unittest.main()