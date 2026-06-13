"""Unit tests for Anthropic explicit cache support in _convert_content_to_anthropic."""

import unittest

from linhai.llm.anthropic_compatible import _convert_content_to_anthropic
from linhai.agent.message import ExplicitCacheMessage


class TestAnthropicExplicitCache(unittest.TestCase):

    def test_explicit_cache_message_preserves_cache_control(self):
        msg = ExplicitCacheMessage("hello world")
        llm_msg = msg.to_llm_message()
        content = llm_msg.get("content")
        assert isinstance(content, list)
        result = _convert_content_to_anthropic(content)
        assert isinstance(result, list)
        self.assertEqual(len(result), 1)
        block = result[0]
        self.assertEqual(block["type"], "text")
        self.assertEqual(block["text"], "hello world")
        self.assertIn("cache_control", block)
        self.assertEqual(block["cache_control"], {"type": "ephemeral"})

    def test_plain_text_list_no_cache_control(self):
        content = [{"type": "text", "text": "plain message"}]
        result = _convert_content_to_anthropic(content)
        assert isinstance(result, list)
        self.assertEqual(len(result), 1)
        block = result[0]
        self.assertEqual(block["type"], "text")
        self.assertEqual(block["text"], "plain message")
        self.assertNotIn("cache_control", block)

    def test_string_content_no_cache_control(self):
        result = _convert_content_to_anthropic("hello")
        assert isinstance(result, str)
        self.assertEqual(result, "hello")

    def test_mixed_list_one_with_cache_control(self):
        content = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "third"},
        ]
        result = _convert_content_to_anthropic(content)
        assert isinstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertNotIn("cache_control", result[0])
        self.assertEqual(result[0]["text"], "first")
        self.assertIn("cache_control", result[1])
        self.assertEqual(result[1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(result[1]["text"], "second")
        self.assertNotIn("cache_control", result[2])
        self.assertEqual(result[2]["text"], "third")

    def test_empty_text_block_skipped(self):
        content = [{"type": "text", "text": "", "cache_control": {"type": "ephemeral"}}]
        result = _convert_content_to_anthropic(content)
        assert isinstance(result, list)
        self.assertEqual(len(result), 0)

    def test_unknown_part_types_ignored(self):
        content = [{"type": "unknown", "data": "test"}]
        result = _convert_content_to_anthropic(content)
        assert isinstance(result, list)
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
