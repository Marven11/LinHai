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
[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.llm), 1)
        self.assertEqual(config.llm[0].name, "primary")
        self.assertEqual(config.llm[0].base_url, "https://api.example.com")
        self.assertEqual(config.llm[0].api_key, "test_key")
        self.assertEqual(config.llm[0].model, "test_model")

    @patch("pathlib.Path.open")
    def test_load_config_invalid_url(self, mock_open):
        """Test loading a config with invalid URL."""
        config_content = b"""
[[llm]]
name = "primary"
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
[[llm]]
name = "test_llm"
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
[[llm]]
name = "test_llm"
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
[[llm]]
name = "test_llm"
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
        self.assertEqual(config.llm[0].base_url, "https://api.example.com")
        self.assertIsNotNone(config.agent)
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 30000.0)
        self.assertEqual(config.agent.compress_threshold_hard, 60000.0)
        self.assertIsNotNone(config.memory)
        assert config.memory is not None
        self.assertEqual(config.memory.file_path, "./test_memory.md")
        self.assertIsNotNone(config.tools)
        assert config.tools is not None
        self.assertEqual(config.tools.max_output_length, 2000)

    @patch("pathlib.Path.open")
    def test_load_config_with_int_values(self, mock_open):
        """Test loading a config with integer values for compress thresholds."""
        config_content = b"""
[[llm]]
name = "test_llm"
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
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 30000)
        self.assertEqual(config.agent.compress_threshold_hard, 60000)

    @patch("pathlib.Path.open")
    def test_load_config_with_float_values(self, mock_open):
        """Test loading a config with float values for compress thresholds."""
        config_content = b"""
[[llm]]
name = "test_llm"
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
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 0.5)
        self.assertEqual(config.agent.compress_threshold_hard, 0.8)

    @patch("pathlib.Path.open")
    def test_load_config_with_defaults(self, mock_open):
        """Test loading a config with default values."""
        config_content = b"""
[[llm]]
name = "test_llm"
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

    @patch("pathlib.Path.open")
    def test_load_config_multiple_llms(self, mock_open):
        """Test loading a config with multiple LLMs."""
        config_content = b"""
[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "secondary"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.llm), 2)

        # 验证第一个LLM
        self.assertEqual(config.llm[0].name, "primary")
        self.assertEqual(config.llm[0].base_url, "https://api.example.com")
        self.assertEqual(config.llm[0].api_key, "test_key_1")
        self.assertEqual(config.llm[0].model, "test_model_1")

        # 验证第二个LLM
        self.assertEqual(config.llm[1].name, "secondary")
        self.assertEqual(config.llm[1].base_url, "https://api.example.org")
        self.assertEqual(config.llm[1].api_key, "test_key_2")
        self.assertEqual(config.llm[1].model, "test_model_2")

    @patch("pathlib.Path.open")
    def test_load_config_multiple_llms_with_optional_fields(self, mock_open):
        """Test loading a config with multiple LLMs and optional fields."""
        config_content = b"""
[[llm]]
name = "main"
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"

[[llm]]
name = "backup"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"

[agent]
compress_threshold_soft = 0.5
compress_threshold_hard = 0.8

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
        self.assertEqual(len(config.llm), 2)

        # 验证LLMs
        self.assertEqual(config.llm[0].name, "main")
        self.assertEqual(config.llm[1].name, "backup")

        # 验证可选字段
        self.assertIsNotNone(config.agent)
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 0.5)
        self.assertEqual(config.agent.compress_threshold_hard, 0.8)
        self.assertIsNotNone(config.memory)
        assert config.memory is not None
        self.assertEqual(config.memory.file_path, "./test_memory.md")
        self.assertIsNotNone(config.tools)
        assert config.tools is not None
        self.assertEqual(config.tools.max_output_length, 2000)

    @patch("pathlib.Path.open")
    def test_load_config_multiple_llms_invalid_name(self, mock_open):
        """Test loading a config with multiple LLMs with empty name."""
        config_content = b"""
[[llm]]
name = ""
base_url = "https://api.example.com"
api_key = "test_key_1"
model = "test_model_1"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()


if __name__ == "__main__":
    unittest.main()
    @patch("pathlib.Path.open")
    def test_load_config_valid_name(self, mock_open):
        """Test loading a config with valid LLM names."""
        config_content = b"""
[[llm]]
name = "test-llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"

[[llm]]
name = "test_llm"
base_url = "https://api.example.org"
api_key = "test_key_2"
model = "test_model_2"

[[llm]]
name = "test123"
base_url = "https://api.example.net"
api_key = "test_key_3"
model = "test_model_3"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.llm), 3)
        self.assertEqual(config.llm[0].name, "test-llm")
        self.assertEqual(config.llm[1].name, "test_llm")
        self.assertEqual(config.llm[2].name, "test123")

    @patch("pathlib.Path.open")
    def test_load_config_invalid_name_with_space(self, mock_open):
        """Test loading a config with invalid LLM name containing space."""
        config_content = b"""
[[llm]]
name = "test llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("pathlib.Path.open")
    def test_load_config_invalid_name_with_special_char(self, mock_open):
        """Test loading a config with invalid LLM name containing special character."""
        config_content = b"""
[[llm]]
name = "test@llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("pathlib.Path.open")
    def test_load_config_invalid_name_with_dot(self, mock_open):
        """Test loading a config with invalid LLM name containing dot."""
        config_content = b"""
[[llm]]
name = "test.llm"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"
"""
        mock_open.return_value.__enter__ = mock_open.return_value
        mock_open.return_value.__exit__ = lambda self, *args: None
        mock_open.return_value.read.return_value = config_content

        with self.assertRaises(ConfigValidationError):
            load_config()