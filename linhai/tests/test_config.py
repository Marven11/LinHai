"""Unit tests for the config module."""

import unittest
from unittest.mock import patch, mock_open
import tomllib

from linhai.config import ConfigValidationError, load_config


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
        self.assertIsInstance(config, dict)
        self.assertEqual(config["llm"]["base_url"], "https://api.example.com")
        self.assertEqual(config["llm"]["api_key"], "test_key")
        self.assertEqual(config["llm"]["model"], "test_model")

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


if __name__ == "__main__":
    unittest.main()
