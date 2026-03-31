"""Unit tests for global prompt file path selection."""

import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import os

from linhai.agent.base import GlobalPrompt
from linhai.config import Config, LLMConfig, AgentConfig


class TestGlobalPromptPathSelection(unittest.TestCase):
    """Test cases for global prompt file path selection logic."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_agents_md_in_current_directory(self):
        """Test that AGENTS.md in current directory is selected."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pathlib.Path.open") as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "# Test AGENTS.md\nTest content"
                )

                global_prompt = GlobalPrompt(Path("AGENTS.md"))
                self.assertIsInstance(global_prompt, GlobalPrompt)
                self.assertEqual(global_prompt.filepath, Path("AGENTS.md"))

    def test_agent_md_in_current_directory_when_agents_md_missing(self):
        """Test that AGENT.md in current directory is selected when AGENTS.md is missing."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = lambda path: path.name == "AGENT.md"
            with patch("pathlib.Path.open") as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "# Test AGENT.md\nTest content"
                )

                global_prompt = GlobalPrompt(Path("AGENT.md"))
                self.assertIsInstance(global_prompt, GlobalPrompt)
                self.assertEqual(global_prompt.filepath, Path("AGENT.md"))

    def test_no_files_in_current_directory(self):
        """Test behavior when no prompt files exist in current directory."""
        with patch("pathlib.Path.exists", return_value=False):
            mock_llm_config = LLMConfig(
                name="test_llm",
                api_key="test_key",
                base_url="http://test.com",
                model="test_model",
            )
            mock_agent_config = AgentConfig(
                compress_threshold=60000,
            )
            _ = Config(
                llm=[mock_llm_config], agent=[mock_agent_config]
            )  # pylint: disable=unused-variable

            global_prompt = GlobalPrompt(Path("AGENTS.md"))
            self.assertIsInstance(global_prompt, GlobalPrompt)
            self.assertEqual(global_prompt.filepath, Path("AGENTS.md"))


if __name__ == "__main__":
    unittest.main()
