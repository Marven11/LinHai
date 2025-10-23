"""Unit tests for the config module."""

import unittest
from unittest.mock import patch, mock_open
import tomllib

from linhai.config import ConfigValidationError, load_config, Config


class TestConfig(unittest.TestCase):
    """Test cases for the config module."""

    @patch("pathlib.Path.open")
    def test_load_config_valid(self, mock_open):
        """Test loading a valid config."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(config.llm.base_url, "https://api.example.com")
        self.assertEqual(config.llm.api_key, "test_key")
        self.assertEqual(config.llm.model, "test_model")

    @patch("pathlib.Path.open")
    def test_load_config_invalid_url(self, mock_open):
        """Test loading a config with invalid URL."""
        config_content = b"""
[llm]
base_url = "invalid_url"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("pathlib.Path.open")
    def test_load_config_empty_api_key(self, mock_open):
        """Test loading a config with empty API key."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = ""
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("pathlib.Path.open")
    def test_load_config_empty_model(self, mock_open):
        """Test loading a config with empty model."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = ""
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("pathlib.Path.open")
    def test_load_config_with_optional_fields(self, mock_open):
        """Test loading a config with optional fields."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 30000
compress_threshold_hard = 60000

[memory]
file_path = "./test_memory.md"

[tools]
max_output_length = 2000
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(config.llm.base_url, "https://api.example.com")
        self.assertIsNotNone(config.agent)
        self.assertEqual(config.agent.compress_threshold_soft, 30000.0)
        self.assertEqual(config.agent.compress_threshold_hard, 60000.0)
        self.assertIsNotNone(config.memory)
        self.assertEqual(config.memory.file_path, "./test_memory.md")
        self.assertIsNotNone(config.tools)
        self.assertEqual(config.tools.max_output_length, 2000)

    @patch("pathlib.Path.open")
    def test_load_config_with_int_values(self, mock_open):
        """Test loading a config with integer values for compress thresholds."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 30000
compress_threshold_hard = 60000
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIsNotNone(config.agent)
        self.assertEqual(config.agent.compress_threshold_soft, 30000)
        self.assertEqual(config.agent.compress_threshold_hard, 60000)

    @patch("pathlib.Path.open")
    def test_load_config_with_float_values(self, mock_open):
        """Test loading a config with float values for compress thresholds."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[agent]
compress_threshold_soft = 0.5
compress_threshold_hard = 0.8
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIsNotNone(config.agent)
        self.assertEqual(config.agent.compress_threshold_soft, 0.5)
        self.assertEqual(config.agent.compress_threshold_hard, 0.8)

    @patch("pathlib.Path.open")
    def test_load_config_with_defaults(self, mock_open):
        """Test loading a config with default values."""
        config_content = b"""
[llm]
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        # 检查默认值
        self.assertIsNone(config.agent)
        self.assertIsNone(config.memory)
        self.assertIsNone(config.tools)


if __name__ == "__main__":
    unittest.main()
