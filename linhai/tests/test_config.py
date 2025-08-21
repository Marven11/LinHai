"""Unit tests for the config module."""
import unittest
from unittest.mock import patch

from linhai.config import ConfigValidationError, load_config


class TestConfig(unittest.TestCase):
    """Test cases for the config module."""
    @patch("toml.load")
    def test_load_config_valid(self, mock_toml):
        """Test loading a valid config."""
        mock_toml.return_value = {
            "llm": {
                "base_url": "https://api.example.com",
                "api_key": "test_key",
                "model": "test_model",
            }
        }
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertEqual(config["llm"]["base_url"], "https://api.example.com")
        self.assertEqual(config["llm"]["api_key"], "test_key")
        self.assertEqual(config["llm"]["model"], "test_model")

    @patch("toml.load")
    def test_load_config_invalid_url(self, mock_toml):
        """Test loading a config with invalid URL."""
        mock_toml.return_value = {
            "llm": {
                "base_url": "invalid_url",
                "api_key": "test_key",
                "model": "test_model",
            }
        }
        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("toml.load")
    def test_load_config_empty_api_key(self, mock_toml):
        """Test loading a config with empty API key."""
        mock_toml.return_value = {
            "llm": {
                "base_url": "https://api.example.com",
                "api_key": "",
                "model": "test_model",
            }
        }
        with self.assertRaises(ConfigValidationError):
            load_config()

    @patch("toml.load")
    def test_load_config_empty_model(self, mock_toml):
        """Test loading a config with empty model."""
        mock_toml.return_value = {
            "llm": {
                "base_url": "https://api.example.com",
                "api_key": "test_key",
                "model": "",
            }
        }
        with self.assertRaises(ConfigValidationError):
            load_config()


if __name__ == "__main__":
    unittest.main()
