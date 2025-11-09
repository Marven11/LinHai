"""Unit tests for the LLM module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.llm import AnswerToken, AnswerTokenUsage, ChatMessage, OpenAi


class TestLLM(unittest.IsolatedAsyncioTestCase):
    """Test cases for the LLM classes."""

    def setUp(self):
        # 创建模拟的OpenAi实例
        self.llm = OpenAi(
            api_key="test_key",
            base_url="https://test.com",
            model="test_model",
            openai_config={},
            chat_completion_kwargs={},
        )

    def test_chat_message_creation(self):
        """Test ChatMessage creation and conversion."""
        msg = ChatMessage(role="user", message="Hello")
        chat_msg = msg.to_llm_message()
        self.assertEqual(chat_msg.get("role"), "user")
        self.assertEqual(chat_msg.get("content"), "<user>Hello</user>")

    async def test_openai_answer_stream(self):
        """Test basic functionality of answer_stream."""
        # 创建完全mock的OpenAI客户端
        mock_client = MagicMock()

        # 创建模拟的流响应 - 创建一个真正的异步迭代器
        class MockStream:
            """Mock stream for testing OpenAI answer stream."""
            def __init__(self):
                self.chunks = [
                    self._create_chunk("Hello"),
                    self._create_chunk(" World"),
                ]
                self.index = 0

            def _create_chunk(self, content):
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = content
                chunk.choices[0].delta.reasoning_content = None
                return chunk

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                # 模拟异步延迟
                await asyncio.sleep(0.001)
                return chunk

        # 配置mock客户端返回我们的模拟流
        mock_client.chat.completions.create = AsyncMock(return_value=MockStream())

        # 使用patch直接替换openai属性
        with patch.object(self.llm, "openai", mock_client):
            # 运行测试，添加超时控制
            history = [ChatMessage(role="user", message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )

            # 验证流式响应
            content = ""
            tokens = []
            async for token in answer:
                if isinstance(token, AnswerToken):
                    content += token.content
                    tokens.append(token)

            self.assertEqual(content, "Hello World")
            mock_client.chat.completions.create.assert_called_once()

    async def test_openai_answer_interrupt(self):
        """Test interrupt functionality of answer_stream."""
        # 创建完全mock的OpenAI客户端
        mock_client = MagicMock()

        # 创建模拟的流响应 - 创建一个真正的异步迭代器
        class MockStream:
            """Mock stream for testing OpenAI answer stream."""
            def __init__(self):
                self.chunks = [
                    self._create_chunk("Hello"),
                    self._create_chunk(" World"),
                ]
                self.index = 0

            def _create_chunk(self, content):
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = content
                chunk.choices[0].delta.reasoning_content = None
                return chunk

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                # 模拟异步延迟
                await asyncio.sleep(0.001)
                return chunk

        # 配置mock客户端返回我们的模拟流
        mock_client.chat.completions.create = AsyncMock(return_value=MockStream())

        # 使用patch直接替换openai属性
        with patch.object(self.llm, "openai", mock_client):
            # 运行测试，添加超时控制
            history = [ChatMessage(role="user", message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )

            # 收集流式响应并在中途中断
            content = ""
            token_count = 0
            async for token in answer:
                if isinstance(token, AnswerToken):
                    content += token.content
                    token_count += 1
                    if token_count == 1:
                        answer.interrupt()
                        break

            self.assertEqual(content, "Hello")
            mock_client.chat.completions.create.assert_called_once()

    def test_openai_initialization(self):
        """Test OpenAi initialization."""
        self.assertEqual(self.llm.model, "test_model")

    @patch("openai.AsyncOpenAI")
    async def test_openai_error_handling(self, mock_openai_class):
        """Test error handling in OpenAi."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_openai_class.return_value = mock_client

        with self.assertRaises(Exception):
            history = [ChatMessage(role="user", message="Hi")]
            # 添加超时控制
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )
            async for _ in answer:
                pass

    def test_answer_token(self):
        """Test AnswerToken class with pydantic."""
        # Test AnswerToken with reasoning content
        token1 = AnswerToken(
            reasoning_content="Let me think...", content="The answer is 42"
        )
        self.assertEqual(token1.reasoning_content, "Let me think...")
        self.assertEqual(token1.content, "The answer is 42")

        # Test AnswerToken without reasoning content
        token2 = AnswerToken(content="Hello world")
        self.assertIsNone(token2.reasoning_content)
        self.assertEqual(token2.content, "Hello world")

        # Test AnswerToken with empty content
        token3 = AnswerToken(reasoning_content="Thinking...", content="")
        self.assertEqual(token3.reasoning_content, "Thinking...")
        self.assertEqual(token3.content, "")

    async def test_kimi_token_estimation(self):
        """Test Kimi token estimation functionality."""
        # 创建支持Kimi兼容性的OpenAi实例
        kimi_llm = OpenAi(
            api_key="kimi_test_key",
            base_url="https://api.moonshot.cn/v1",
            model="kimi-k2-turbo-preview",
            openai_config={},
            chat_completion_kwargs={},
            compatibility="kimi",
        )

        # Mock httpx client for token estimation
        with patch("linhai.llm.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": {"total_tokens": 100}}
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            history = [ChatMessage(role="user", message="Hello")]
            result = await kimi_llm.estimate_token_count(history)

            self.assertIsNotNone(result)
            self.assertEqual(result.total_tokens, 100)
            self.assertEqual(result.input_tokens, 100)
            self.assertEqual(result.output_tokens, 0)

    async def test_non_kimi_token_estimation(self):
        """Test that non-Kimi LLMs return None for token estimation."""
        history = [ChatMessage(role="user", message="Hello")]
        result = await self.llm.estimate_token_count(history)
        self.assertIsNone(result)

    async def test_kimi_token_estimation_error_handling(self):
        """Test Kimi token estimation error handling."""
        kimi_llm = OpenAi(
            api_key="kimi_test_key",
            base_url="https://api.moonshot.cn/v1",
            model="kimi-k2-turbo-preview",
            openai_config={},
            chat_completion_kwargs={},
            compatibility="kimi",
        )

        # Mock httpx client to raise an exception
        with patch("linhai.llm.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client_class.return_value = mock_client

            history = [ChatMessage(role="user", message="Hello")]
            result = await kimi_llm.estimate_token_count(history)

            # Should return None on error
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
