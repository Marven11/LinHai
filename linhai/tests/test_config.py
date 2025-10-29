"""Unit tests for the config module."""

import unittest
from unittest.mock import patch

from linhai.config import ConfigValidationError, load_config, Config


class TestConfig(unittest.TestCase):
    """Test cases for the config module."""

    @patch("linhai.config.tomllib.load")
    def test_load_config_valid(self, mock_tomllib_load):
        """Test loading a valid config."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "primary",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ]
        }

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.llm), 1)
        self.assertEqual(config.llm[0].name, "primary")
        self.assertEqual(config.llm[0].base_url, "https://api.example.com")
        self.assertEqual(config.llm[0].api_key, "test_key")
        self.assertEqual(config.llm[0].model, "test_model")

    @patch("linhai.config.tomllib.load")
    def test_load_config_invalid_url(self, mock_tomllib_load):
        """Test loading a config with invalid URL."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "primary",
                    "base_url": "invalid_url",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ]
        }

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("linhai.config.tomllib.load")
    def test_load_config_empty_api_key(self, mock_tomllib_load):
        """Test loading a config with empty API key."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "",
                    "model": "test_model"
                }
            ]
        }

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("linhai.config.tomllib.load")
    def test_load_config_empty_model(self, mock_tomllib_load):
        """Test loading a config with empty model."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": ""
                }
            ]
        }

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("linhai.config.tomllib.load")
    def test_load_config_with_optional_fields(self, mock_tomllib_load):
        """Test loading a config with optional fields."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ],
            "agent": {
                "compress_threshold_soft": 30000,
                "compress_threshold_hard": 60000
            },
            "memory": {
                "file_path": "./test_memory.md"
            },
            "tools": {
                "max_output_length": 2000
            }
        }

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

    @patch("linhai.config.tomllib.load")
    def test_load_config_with_int_values(self, mock_tomllib_load):
        """Test loading a config with integer values for compress thresholds."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ],
            "agent": {
                "compress_threshold_soft": 30000,
                "compress_threshold_hard": 60000
            }
        }

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIsNotNone(config.agent)
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 30000)
        self.assertEqual(config.agent.compress_threshold_hard, 60000)

    @patch("linhai.config.tomllib.load")
    def test_load_config_with_float_values(self, mock_tomllib_load):
        """Test loading a config with float values for compress thresholds."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ],
            "agent": {
                "compress_threshold_soft": 0.5,
                "compress_threshold_hard": 0.8
            }
        }

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIsNotNone(config.agent)
        assert config.agent is not None
        self.assertEqual(config.agent.compress_threshold_soft, 0.5)
        self.assertEqual(config.agent.compress_threshold_hard, 0.8)

    @patch("linhai.config.tomllib.load")
    def test_load_config_with_defaults(self, mock_tomllib_load):
        """Test loading a config with default values."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "test_llm",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key",
                    "model": "test_model"
                }
            ]
        }

        config = load_config()
        self.assertIsInstance(config, Config)
        # 检查默认值
        self.assertIsNone(config.agent)
        self.assertIsNone(config.memory)
        self.assertIsNone(config.tools)

    @patch("linhai.config.tomllib.load")
    def test_load_config_multiple_llms(self, mock_tomllib_load):
        """Test loading a config with multiple LLMs."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "primary",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key_1",
                    "model": "test_model_1"
                },
                {
                    "name": "secondary",
                    "base_url": "https://api.example.org",
                    "api_key": "test_key_2",
                    "model": "test_model_2"
                }
            ]
        }

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

    @patch("linhai.config.tomllib.load")
    def test_load_config_multiple_llms_with_optional_fields(self, mock_tomllib_load):
        """Test loading a config with multiple LLMs and optional fields."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "main",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key_1",
                    "model": "test_model_1"
                },
                {
                    "name": "backup",
                    "base_url": "https://api.example.org",
                    "api_key": "test_key_2",
                    "model": "test_model_2"
                }
            ],
            "agent": {
                "compress_threshold_soft": 0.5,
                "compress_threshold_hard": 0.8
            },
            "memory": {
                "file_path": "./test_memory.md"
            },
            "tools": {
                "max_output_length": 2000
            }
        }

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

    @patch("linhai.config.tomllib.load")
    def test_load_config_multiple_llms_invalid_name(self, mock_tomllib_load):
        """Test loading a config with multiple LLMs with empty name."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "",
                    "base_url": "https://api.example.com",
                    "api_key": "test_key_1",
                    "model": "test_model_1"
                }
            ]
        }

        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("linhai.config.tomllib.load")
    def test_load_config_with_openai_kwargs(self, mock_tomllib_load):
        """Test loading a config with client_options and completion_options."""
        mock_tomllib_load.return_value = {
            "llm": [
                {
                    "name": "qwen",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "api_key": "test_key",
                    "model": "qwen-plus",
                    "client_options": {
                        "timeout": 30
                    },
                    "completion_options": {
                        "stream_options": {
                            "include_usage": True
                        }
                    }
                }
            ]
        }

        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(len(config.llm), 1)
        self.assertEqual(config.llm[0].name, "qwen")
        self.assertEqual(
            config.llm[0].base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.assertEqual(config.llm[0].api_key, "test_key")
        self.assertEqual(config.llm[0].model, "qwen-plus")
        self.assertEqual(config.llm[0].client_options, {"timeout": 30})
        self.assertEqual(
            config.llm[0].completion_options,
            {"stream_options": {"include_usage": True}},
        )


if __name__ == "__main__":
    unittest.main()
