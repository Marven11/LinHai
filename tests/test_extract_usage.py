import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from linhai.llm import extract_usage, AnswerTokenUsage


class TestExtractUsage(unittest.TestCase):

    def test_deepseek_format(self):
        result = extract_usage(
            {
                "prompt_tokens": 5,
                "completion_tokens": 34,
                "total_tokens": 39,
                "prompt_tokens_details": {"cached_tokens": 0},
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 5,
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.input_tokens, 5)
        self.assertEqual(result.output_tokens, 34)
        self.assertEqual(result.total_tokens, 39)
        self.assertEqual(result.cached_input_tokens, 0)
        self.assertIsNone(result.cache_creation_input_tokens)

    def test_kimi_k25_format(self):
        result = extract_usage(
            {
                "prompt_tokens": 8,
                "completion_tokens": 177,
                "total_tokens": 185,
                "cached_tokens": 8,
                "prompt_tokens_details": {"cached_tokens": 8},
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.input_tokens, 8)
        self.assertEqual(result.output_tokens, 177)
        self.assertEqual(result.total_tokens, 185)
        self.assertEqual(result.cached_input_tokens, 8)
        self.assertIsNone(result.cache_creation_input_tokens)

    def test_qwen_format(self):
        details = SimpleNamespace(cached_tokens=0, cache_creation_input_tokens=5)
        result = extract_usage(
            {
                "total_tokens": 20,
                "completion_tokens": 11,
                "prompt_tokens": 9,
                "prompt_tokens_details": details,
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.input_tokens, 9)
        self.assertEqual(result.output_tokens, 11)
        self.assertEqual(result.total_tokens, 20)
        self.assertEqual(result.cached_input_tokens, 0)
        self.assertEqual(result.cache_creation_input_tokens, 5)

    def test_qwen_format_fallback_cache_write_tokens(self):
        details = SimpleNamespace(
            cached_tokens=3, cache_creation_input_tokens=None, cache_write_tokens=7
        )
        result = extract_usage(
            {
                "total_tokens": 20,
                "completion_tokens": 11,
                "prompt_tokens": 9,
                "prompt_tokens_details": details,
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.cache_creation_input_tokens, 7)

    def test_kimi_k2_thinking_fallback(self):
        result = extract_usage(
            {
                "prompt_tokens": 8,
                "completion_tokens": 91,
                "total_tokens": 99,
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.input_tokens, 8)
        self.assertEqual(result.output_tokens, 91)
        self.assertEqual(result.total_tokens, 99)
        self.assertIsNone(result.cached_input_tokens)
        self.assertIsNone(result.cache_creation_input_tokens)

    def test_missing_fields_returns_none(self):
        self.assertIsNone(extract_usage({}))
        self.assertIsNone(extract_usage({"prompt_tokens": 5}))

    def test_prompt_tokens_details_dict(self):
        result = extract_usage(
            {
                "prompt_tokens": 9,
                "completion_tokens": 11,
                "total_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 4},
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.cached_input_tokens, 4)

    def test_prompt_tokens_details_without_cached_tokens(self):
        result = extract_usage(
            {
                "prompt_tokens": 9,
                "completion_tokens": 11,
                "total_tokens": 20,
                "prompt_tokens_details": {},
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsNone(result.cached_input_tokens)


if __name__ == "__main__":
    unittest.main()
