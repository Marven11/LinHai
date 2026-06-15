"""Unit tests for AnthropicAnswer message_delta cache info extraction."""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.registry import Registry
from linhai.llm.anthropic_compatible import AnthropicAnswer


class TestAnthropicAnswerMessageDelta(unittest.IsolatedAsyncioTestCase):

    async def test_message_delta_extracts_cache_info(self):
        registry = Registry()
        mock_stream = AsyncMock()

        answer = AnthropicAnswer(
            stream=mock_stream,
            registry=registry,
            llm_instance=None,
            estimated_cached_input_tokens=0,
        )

        mock_msg_start = MagicMock()
        mock_msg_start.type = "message_start"
        mock_msg_start.message = MagicMock()
        mock_msg_start.message.usage = MagicMock(
            input_tokens=1000,
            output_tokens=0,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
        )

        mock_content_delta = MagicMock()
        mock_content_delta.type = "content_block_delta"
        mock_content_delta.delta = MagicMock()
        mock_content_delta.delta.type = "text_delta"
        mock_content_delta.delta.text = "hello"

        mock_msg_delta = MagicMock()
        mock_msg_delta.type = "message_delta"
        mock_msg_delta.usage = MagicMock(
            input_tokens=1974,
            output_tokens=476,
            cache_read_input_tokens=28032,
            cache_creation_input_tokens=0,
        )

        mock_msg_stop = MagicMock()
        mock_msg_stop.type = "message_stop"

        mock_stream.__anext__.side_effect = [
            mock_msg_start,
            mock_content_delta,
            mock_msg_delta,
            mock_msg_stop,
            None,
        ]

        await answer.update_toyield()
        await answer.update_toyield()
        await answer.update_toyield()

        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.cached_input_tokens, 28032)
        self.assertIsNone(usage.cache_creation_input_tokens)
        self.assertEqual(usage.output_tokens, 476)
        self.assertEqual(usage.input_tokens, 1974 + 28032)
        self.assertEqual(usage.total_tokens, 1974 + 28032 + 476)

    async def test_message_delta_cache_creation_tokens(self):
        registry = Registry()
        mock_stream = AsyncMock()

        answer = AnthropicAnswer(
            stream=mock_stream,
            registry=registry,
            llm_instance=None,
            estimated_cached_input_tokens=0,
        )

        mock_msg_start = MagicMock()
        mock_msg_start.type = "message_start"
        mock_msg_start.message = MagicMock()
        mock_msg_start.message.usage = MagicMock(
            input_tokens=500,
            output_tokens=0,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
        )

        mock_msg_delta = MagicMock()
        mock_msg_delta.type = "message_delta"
        mock_msg_delta.usage = MagicMock(
            input_tokens=600,
            output_tokens=200,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=15000,
        )

        mock_stream.__anext__.side_effect = [
            mock_msg_start,
            mock_msg_delta,
            None,
        ]

        await answer.update_toyield()
        await answer.update_toyield()

        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertIsNone(usage.cached_input_tokens)
        self.assertEqual(usage.cache_creation_input_tokens, 15000)
        self.assertEqual(usage.input_tokens, 600 + 15000)

    async def test_message_start_has_cache_message_delta_replaces(self):
        registry = Registry()
        mock_stream = AsyncMock()

        answer = AnthropicAnswer(
            stream=mock_stream,
            registry=registry,
            llm_instance=None,
            estimated_cached_input_tokens=0,
        )

        mock_msg_start = MagicMock()
        mock_msg_start.type = "message_start"
        mock_msg_start.message = MagicMock()
        mock_msg_start.message.usage = MagicMock(
            input_tokens=800,
            output_tokens=0,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=None,
        )

        mock_msg_delta = MagicMock()
        mock_msg_delta.type = "message_delta"
        mock_msg_delta.usage = MagicMock(
            input_tokens=1974,
            output_tokens=476,
            cache_read_input_tokens=28032,
            cache_creation_input_tokens=0,
        )

        mock_stream.__anext__.side_effect = [
            mock_msg_start,
            mock_msg_delta,
            None,
        ]

        await answer.update_toyield()
        await answer.update_toyield()

        usage = answer.get_token_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.cached_input_tokens, 28032)
        self.assertEqual(usage.output_tokens, 476)
        self.assertEqual(usage.input_tokens, 1974 + 28032)


if __name__ == "__main__":
    unittest.main()
