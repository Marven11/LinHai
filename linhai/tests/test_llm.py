import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from linhai.llm import OpenAi, ChatMessage


class TestLLM(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 创建模拟的OpenAi实例
        self.llm = OpenAi(
            api_key="test-key",
            base_url="https://test.com",
            model="test-model",
            openai_config={},
        )

    def tearDown(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_chat_message_creation(self):
        """测试ChatMessage类的创建和转换功能"""
        msg = ChatMessage(role="user", message="Hello")
        chat_msg = msg.to_chat_message()
        self.assertEqual(chat_msg.get("role"), "user")
        self.assertEqual(chat_msg.get("content"), "Hello")

    @patch("openai.AsyncOpenAI")
    async def test_openai_answer_stream(self, mock_openai_class):
        """测试OpenAi answer_stream的基本功能"""
        # 创建模拟的流响应
        mock_stream = AsyncMock()
        mock_chunk1 = AsyncMock()
        mock_chunk1.choices = [AsyncMock()]
        mock_chunk1.choices[0].delta.content = "Hello"

        mock_chunk2 = AsyncMock()
        mock_chunk2.choices = [AsyncMock()]
        mock_chunk2.choices[0].delta.content = " World"

        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2]

        # 配置mock客户端
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
        mock_openai_class.return_value = mock_client

        history = [ChatMessage(role="user", message="Hi")]
        answer = await self.llm.answer_stream(history)

        # 收集流式响应
        content = ""
        async for token in answer:
            content += token["content"]

        self.assertEqual(content, "Hello World")

    @patch("openai.AsyncOpenAI")
    async def test_openai_answer_interrupt(self, mock_openai_class):
        """测试OpenAi answer_stream的中断功能"""
        # 创建模拟的流响应
        mock_stream = AsyncMock()
        mock_chunk1 = AsyncMock()
        mock_chunk1.choices = [AsyncMock()]
        mock_chunk1.choices[0].delta.content = "Hello"

        mock_chunk2 = AsyncMock()
        mock_chunk2.choices = [AsyncMock()]
        mock_chunk2.choices[0].delta.content = " World"

        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2]

        # 配置mock客户端
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
        mock_openai_class.return_value = mock_client

        history = [ChatMessage(role="user", message="Hi")]
        answer = await self.llm.answer_stream(history)

        # 收集流式响应并在中途中断
        content = ""
        token_count = 0
        async for token in answer:
            content += token["content"]
            token_count += 1
            if token_count == 2:
                answer.interrupt()
                break

        self.assertEqual(content, "Hello World")

    def test_openai_initialization(self):
        """测试OpenAi类的初始化"""
        self.assertEqual(self.llm.model, "test-model")

    @patch("openai.AsyncOpenAI")
    async def test_openai_empty_history(self, mock_openai_class):
        """测试空历史记录的情况"""
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = []

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)
        mock_openai_class.return_value = mock_client

        answer = await self.llm.answer_stream([])
        content = ""
        async for token in answer:
            content += token["content"]
        self.assertEqual(content, "")

    @patch("openai.AsyncOpenAI")
    async def test_openai_error_handling(self, mock_openai_class):
        """测试错误处理情况"""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_openai_class.return_value = mock_client

        with self.assertRaises(Exception):
            history = [ChatMessage(role="user", message="Hi")]
            answer = await self.llm.answer_stream(history)
            async for _ in answer:
                pass


if __name__ == "__main__":
    unittest.main()
