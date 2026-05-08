import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from linhai.llm import OpenAi


class TestOpenAiTimeoutConfig(unittest.IsolatedAsyncioTestCase):
    def test_timeout_max_retries_removed_from_config(self):
        with patch("linhai.llm.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            openai = OpenAi(
                registry=MagicMock(),
                api_key="key",
                base_url="http://test",
                model="model",
                openai_config={"timeout": 30, "max_retries": 3, "extra_key": "val"},
                chat_completion_kwargs={},
                support_image=False,
                explicit_cache_info=None,
                name="test",
            )
            call_kwargs = mock_cls.call_args[1]
            self.assertEqual(call_kwargs["timeout"], 10)
            self.assertEqual(call_kwargs["max_retries"], 0)
            self.assertEqual(call_kwargs["extra_key"], "val")
            self.assertNotIn("timeout", openai._openai_config)
            self.assertNotIn("max_retries", openai._openai_config)

    def test_empty_config_uses_defaults(self):
        with patch("linhai.llm.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            OpenAi(
                registry=MagicMock(),
                api_key="key",
                base_url="http://test",
                model="model",
                openai_config={},
                chat_completion_kwargs={},
                support_image=False,
                explicit_cache_info=None,
                name="test",
            )
            call_kwargs = mock_cls.call_args[1]
            self.assertEqual(call_kwargs["timeout"], 10)
            self.assertEqual(call_kwargs["max_retries"], 0)

    async def test_reconnect_no_duplicate_keys(self):
        with patch("linhai.llm.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_cls.return_value = mock_client
            openai = OpenAi(
                registry=MagicMock(),
                api_key="key",
                base_url="http://test",
                model="model",
                openai_config={"timeout": 30},
                chat_completion_kwargs={},
                support_image=False,
                explicit_cache_info=None,
                name="test",
            )
            await openai.reconnect()
            self.assertEqual(mock_cls.call_count, 2)
            call_kwargs = mock_cls.call_args[1]
            self.assertEqual(call_kwargs["timeout"], 10)


if __name__ == "__main__":
    unittest.main()
