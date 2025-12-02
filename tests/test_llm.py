"""Unit tests for the LLM module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.llm import AnswerToken, UserMessage, AssistantMessage, OpenAi


class TestLLM(unittest.IsolatedAsyncioTestCase):
    """Test cases for the LLM classes."""

    def setUp(self):
        self.llm = OpenAi(
            api_key="test_key",
            base_url="https://test.com",
            model="test_model",
            openai_config={},
            chat_completion_kwargs={},
        )

    def test_user_message_creation(self):
        """Test UserMessage creation and conversion."""
        msg = UserMessage(message="Hello")
        chat_msg = msg.to_llm_message()
        self.assertEqual(chat_msg.get("role"), "user")
        self.assertEqual(chat_msg.get("content"), "<<user>>Hello<<user>>")

    async def test_openai_answer_stream(self):
        """Test basic functionality of answer_stream."""
        mock_client = MagicMock()

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
                await asyncio.sleep(0.001)
                return chunk

        mock_client.chat.completions.create = AsyncMock(return_value=MockStream())

        with patch.object(self.llm, "openai", mock_client):
            history = [UserMessage(message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )

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
        mock_client = MagicMock()

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
                await asyncio.sleep(0.001)
                return chunk

        mock_client.chat.completions.create = AsyncMock(return_value=MockStream())

        with patch.object(self.llm, "openai", mock_client):
            history = [UserMessage(message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )

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
            history = [UserMessage(message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history), timeout=5.0
            )
            async for _ in answer:
                pass

    def test_answer_token(self):
        """Test AnswerToken class with pydantic."""
        token1 = AnswerToken(
            reasoning_content="Let me think...", content="The answer is 42"
        )
        self.assertEqual(token1.reasoning_content, "Let me think...")
        self.assertEqual(token1.content, "The answer is 42")

        token2 = AnswerToken(content="Hello world")
        self.assertIsNone(token2.reasoning_content)
        self.assertEqual(token2.content, "Hello world")

        token3 = AnswerToken(reasoning_content="Thinking...", content="")
        self.assertEqual(token3.reasoning_content, "Thinking...")
        self.assertEqual(token3.content, "")




if __name__ == "__main__":
    unittest.main()
