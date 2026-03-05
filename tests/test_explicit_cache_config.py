"""Unit tests for the explicit cache configuration feature."""

import unittest
import tempfile
import os

from linhai.config import load_config, Config, ExplicitCacheConfig


def create_temp_config(config_content: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        return f.name


class TestExplicitCacheConfig(unittest.TestCase):

    def test_default_no_explicit_cache(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertIsNone(config.llm[0].explicit_cache)
        finally:
            os.unlink(temp_file)

    def test_explicit_cache_enabled(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[llm.explicit_cache]
enable = true
cache_write_price_ratio = 1.25
cache_hit_price_ratio = 0.1
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertIsNotNone(config.llm[0].explicit_cache)
            self.assertTrue(config.llm[0].explicit_cache.enable)
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_write_price_ratio, 1.25
            )
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_hit_price_ratio, 0.1
            )
        finally:
            os.unlink(temp_file)

    def test_explicit_cache_disabled(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[llm.explicit_cache]
enable = false
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNotNone(config.llm[0].explicit_cache)
            self.assertFalse(config.llm[0].explicit_cache.enable)
        finally:
            os.unlink(temp_file)

    def test_explicit_cache_default_ratios(self):
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[llm.explicit_cache]
enable = true
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsNotNone(config.llm[0].explicit_cache)
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_write_price_ratio, 1.25
            )
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_hit_price_ratio, 0.1
            )
        finally:
            os.unlink(temp_file)

    def test_explicit_cache_custom_ratios(self):
        config_content = """[[llm]]
name = "claude"
base_url = "https://api.example.com"
api_key = "test_key"
model = "claude-opus"

[llm.explicit_cache]
enable = true
cache_write_price_ratio = 1.5
cache_hit_price_ratio = 0.2
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_write_price_ratio, 1.5
            )
            self.assertAlmostEqual(
                config.llm[0].explicit_cache.cache_hit_price_ratio, 0.2
            )
        finally:
            os.unlink(temp_file)

    def test_multiple_llms_with_mixed_explicit_cache_settings(self):
        config_content = """[[llm]]
name = "llm_with_cache"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[llm.explicit_cache]
enable = true
cache_write_price_ratio = 1.25
cache_hit_price_ratio = 0.1

[[llm]]
name = "llm_without_cache"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"

[[llm]]
name = "llm_disabled_cache"
base_url = "https://api.example.net"
api_key = "test_key_3"
model = "test_model_3"

[llm.explicit_cache]
enable = false
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(len(config.llm), 3)

            self.assertIsNotNone(config.llm[0].explicit_cache)
            self.assertTrue(config.llm[0].explicit_cache.enable)

            self.assertIsNone(config.llm[1].explicit_cache)

            self.assertIsNotNone(config.llm[2].explicit_cache)
            self.assertFalse(config.llm[2].explicit_cache.enable)
        finally:
            os.unlink(temp_file)

    def test_explicit_cache_with_all_other_fields(self):
        config_content = """[[llm]]
name = "complete_llm"
type = "openai"
compatibility = "kimi"
support_image = true
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
token_limit = 8192

[llm.explicit_cache]
enable = true
cache_write_price_ratio = 1.25
cache_hit_price_ratio = 0.1

[llm.client_options]
timeout = 30

[llm.completion_options]
stream_options = { include_usage = true }
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertEqual(len(config.llm), 1)

            llm = config.llm[0]
            self.assertEqual(llm.name, "complete_llm")
            self.assertEqual(llm.type, "openai")
            self.assertEqual(llm.compatibility, "kimi")
            self.assertEqual(llm.support_image, True)
            self.assertIsNotNone(llm.explicit_cache)
            self.assertTrue(llm.explicit_cache.enable)
            self.assertAlmostEqual(llm.explicit_cache.cache_write_price_ratio, 1.25)
            self.assertAlmostEqual(llm.explicit_cache.cache_hit_price_ratio, 0.1)
            self.assertEqual(llm.base_url, "https://api.example.com")
            self.assertEqual(llm.api_key, "test_key")
            self.assertEqual(llm.model, "test_model")
            self.assertEqual(llm.token_limit, 8192)
            self.assertEqual(llm.client_options, {"timeout": 30})
            self.assertEqual(
                llm.completion_options,
                {"stream_options": {"include_usage": True}},
            )
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
