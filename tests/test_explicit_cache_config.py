"""Unit tests for the explicit cache configuration feature."""

import unittest
import tempfile
import os

from linhai.config import load_config, Config


def create_temp_config(config_content: str) -> str:
    """创建临时配置文件并返回路径"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(config_content)
        return f.name


class TestExplicitCacheConfig(unittest.TestCase):
    """Test cases for the explicit cache configuration feature."""

    def test_default_use_explicit_cache_false(self):
        """Test that use_explicit_cache defaults to False."""
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
            self.assertEqual(config.llm[0].use_explicit_cache, False)
        finally:
            os.unlink(temp_file)

    def test_use_explicit_cache_true(self):
        """Test that use_explicit_cache can be set to True."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
use_explicit_cache = true
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].use_explicit_cache, True)
        finally:
            os.unlink(temp_file)

    def test_use_explicit_cache_false(self):
        """Test that use_explicit_cache can be explicitly set to False."""
        config_content = """[[llm]]
name = "test_llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
use_explicit_cache = false
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)
            self.assertEqual(config.llm[0].use_explicit_cache, False)
        finally:
            os.unlink(temp_file)

    def test_multiple_llms_with_mixed_explicit_cache_settings(self):
        """Test multiple LLMs with different use_explicit_cache settings."""
        config_content = """[[llm]]
name = "llm_with_cache"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"
use_explicit_cache = true

[[llm]]
name = "llm_without_cache"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"
use_explicit_cache = false

[[llm]]
name = "llm_default_cache"
base_url = "https://api.example.net"
api_key = "test_key_3"
model = "test_model_3"
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 3)

            self.assertEqual(config.llm[0].name, "llm_with_cache")
            self.assertEqual(config.llm[0].use_explicit_cache, True)

            self.assertEqual(config.llm[1].name, "llm_without_cache")
            self.assertEqual(config.llm[1].use_explicit_cache, False)

            self.assertEqual(config.llm[2].name, "llm_default_cache")
            self.assertEqual(config.llm[2].use_explicit_cache, False)
        finally:
            os.unlink(temp_file)

    def test_use_explicit_cache_with_all_other_fields(self):
        """Test use_explicit_cache works with all other LLM config fields."""
        config_content = """[[llm]]
name = "complete_llm"
type = "openai"
compatibility = "kimi"
support_image = true
use_explicit_cache = true
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
token_limit = 8192

[llm.client_options]
timeout = 30

[llm.completion_options]
stream_options = { include_usage = true }
"""
        temp_file = create_temp_config(config_content)
        try:
            config = load_config(temp_file)
            self.assertIsInstance(config, Config)
            self.assertEqual(len(config.llm), 1)

            llm = config.llm[0]
            self.assertEqual(llm.name, "complete_llm")
            self.assertEqual(llm.type, "openai")
            self.assertEqual(llm.compatibility, "kimi")
            self.assertEqual(llm.support_image, True)
            self.assertEqual(llm.use_explicit_cache, True)
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
