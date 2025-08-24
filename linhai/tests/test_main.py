"""Unit tests for the main module."""

import unittest
from unittest.mock import MagicMock, patch

from linhai.llm import ChatMessage, OpenAi
from linhai.main import chat_loop


class TestMain(unittest.IsolatedAsyncioTestCase):
    """Test cases for the main module."""

    @patch("builtins.input", side_effect=["hello", "quit"])
    @patch("builtins.print")
    async def test_chat_loop(self, mock_print, _mock_input):
        """Test the chat loop functionality."""
        mock_llm = MagicMock(spec=OpenAi)

        # 创建模拟的异步迭代器
        async def mock_aiter():
            yield {"content": "Hi", "reasoning_content": None}

        mock_answer = MagicMock()
        mock_answer.__aiter__.side_effect = mock_aiter
        mock_answer.get_message.return_value = ChatMessage("assistant", "Hi")
        mock_llm.answer_stream.return_value = mock_answer

        await chat_loop(mock_llm)

        mock_llm.answer_stream.assert_called_once()
        mock_print.assert_any_call("\nAI: ", end="", flush=True)
        mock_print.assert_any_call("Hi", end="", flush=True)


if __name__ == "__main__":
    unittest.main()
