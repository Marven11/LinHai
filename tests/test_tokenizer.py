import unittest

from linhai.utils.tokenizer import count_tokens, get_cl100k_base_tokenizer


class TestFakeTokenizer(unittest.TestCase):
    def test_count_tokens_empty(self):
        self.assertEqual(count_tokens(""), 0)

    def test_count_tokens_ascii(self):
        result = count_tokens("hello world")
        self.assertGreater(result, 0)

    def test_count_tokens_unicode(self):
        result = count_tokens("你好世界")
        self.assertGreater(result, 0)

    def test_encode_decode_roundtrip(self):
        tokenizer = get_cl100k_base_tokenizer()
        texts = [
            "hello world",
            "你好世界",
            "",
            "a" * 1000,
            "mix of Chinese and English 123!",
        ]
        for text in texts:
            tokens = tokenizer.encode(text)
            decoded = tokenizer.decode(tokens)
            self.assertEqual(decoded, text, f"Roundtrip failed for: {text[:50]}")

    def test_tiktoken_can_decode_fake_output(self):
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")
        tokenizer = get_cl100k_base_tokenizer()
        texts = [
            "hello world",
            "The quick brown fox jumps over the lazy dog.",
            "a" * 500,
            "mix of Chinese and English 123!",
        ]
        for text in texts:
            tokens = tokenizer.encode(text)
            decoded = enc.decode(tokens)
            self.assertEqual(
                decoded,
                text,
                f"tiktoken failed to decode fake output for: {text[:50]}",
            )


if __name__ == "__main__":
    unittest.main()
