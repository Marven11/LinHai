"""Unit tests for global memory file path selection."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import os

from linhai.agent import create_agent
from linhai.agent_base import GlobalMemory


class TestGlobalMemoryPathSelection(unittest.TestCase):
    """Test cases for global memory file path selection logic."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_linhai_md_in_current_directory(self):
        """Test that LINHAI.md in current directory is selected."""
        # Create LINHAI.md in current directory
        linhai_content = "# Test LINHAI.md\nTest content"
        with open("LINHAI.md", "w", encoding="utf-8") as f:
            f.write(linhai_content)

        # Mock config to avoid actual file operations
        mock_config = {
            "llm": {
                "api_key": "test_key",
                "base_url": "http://test.com",
                "model": "test_model",
                "openai_config": {},
                "chat_completion_kwargs": {},
            },
            "agent": {
                "compress_threshold_hard": 52428,
                "compress_threshold_soft": 32768,
                "tool_confirmation": {
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            },
        }

        with patch("linhai.agent.load_config", return_value=mock_config):
            with patch("linhai.agent.OpenAi") as mock_openai:
                mock_openai.return_value = MagicMock()

                agent, _, _, _, _, _ = create_agent()

                # Check if GlobalMemory is in messages
                global_memory_found = False
                for msg in agent.messages:
                    if isinstance(msg, GlobalMemory):
                        global_memory_found = True
                        # Verify the selected file path
                        self.assertEqual(
                            msg.filepath, Path(self.temp_dir.name) / "LINHAI.md"
                        )
                        break

                self.assertTrue(
                    global_memory_found, "GlobalMemory not found in messages"
                )

    def test_agent_md_in_current_directory(self):
        """Test that AGENT.md in current directory is selected when LINHAI.md is missing."""
        # Create AGENT.md in current directory
        agent_content = "# Test AGENT.md\nTest content"
        with open("AGENT.md", "w", encoding="utf-8") as f:
            f.write(agent_content)

        mock_config = {
            "llm": {
                "api_key": "test_key",
                "base_url": "http://test.com",
                "model": "test_model",
                "openai_config": {},
                "chat_completion_kwargs": {},
            },
            "agent": {
                "compress_threshold_hard": 52428,
                "compress_threshold_soft": 32768,
                "tool_confirmation": {
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            },
        }

        with patch("linhai.agent.load_config", return_value=mock_config):
            with patch("linhai.agent.OpenAi") as mock_openai:
                mock_openai.return_value = MagicMock()

                agent, _, _, _, _, _ = create_agent()

                # Check if GlobalMemory is in messages and selected AGENT.md
                global_memory_found = False
                for msg in agent.messages:
                    if isinstance(msg, GlobalMemory):
                        global_memory_found = True
                        self.assertEqual(
                            msg.filepath, Path(self.temp_dir.name) / "AGENT.md"
                        )
                        break

                self.assertTrue(
                    global_memory_found, "GlobalMemory not found in messages"
                )

    def test_claude_md_in_current_directory(self):
        """Test that CLAUDE.md in current directory is selected when LINHAI.md and AGENT.md are missing."""
        # Create CLAUDE.md in current directory
        claude_content = "# Test CLAUDE.md\nTest content"
        with open("CLAUDE.md", "w", encoding="utf-8") as f:
            f.write(claude_content)

        mock_config = {
            "llm": {
                "api_key": "test_key",
                "base_url": "http://test.com",
                "model": "test_model",
                "openai_config": {},
                "chat_completion_kwargs": {},
            },
            "agent": {
                "compress_threshold_hard": 52428,
                "compress_threshold_soft": 32768,
                "tool_confirmation": {
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            },
        }

        with patch("linhai.agent.load_config", return_value=mock_config):
            with patch("linhai.agent.OpenAi") as mock_openai:
                mock_openai.return_value = MagicMock()

                agent, _, _, _, _, _ = create_agent()

                # Check if GlobalMemory is in messages and selected CLAUDE.md
                global_memory_found = False
                for msg in agent.messages:
                    if isinstance(msg, GlobalMemory):
                        global_memory_found = True
                        self.assertEqual(
                            msg.filepath, Path(self.temp_dir.name) / "CLAUDE.md"
                        )
                        break

                self.assertTrue(
                    global_memory_found, "GlobalMemory not found in messages"
                )

    def test_no_files_in_current_directory(self):
        """Test behavior when no memory files exist in current directory."""
        mock_config = {
            "llm": {
                "api_key": "test_key",
                "base_url": "http://test.com",
                "model": "test_model",
                "openai_config": {},
                "chat_completion_kwargs": {},
            },
            "agent": {
                "compress_threshold_hard": 52428,
                "compress_threshold_soft": 32768,
                "tool_confirmation": {
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            },
        }

        with patch("linhai.agent.load_config", return_value=mock_config):
            with patch("linhai.agent.OpenAi") as mock_openai:
                mock_openai.return_value = MagicMock()

                agent, _, _, _, _, _ = create_agent()

                # Check if GlobalMemory is still added with default path
                global_memory_found = False
                for msg in agent.messages:
                    if isinstance(msg, GlobalMemory):
                        global_memory_found = True
                        # Should use the first path in the list (current directory LINHAI.md)
                        self.assertEqual(
                            msg.filepath, Path(self.temp_dir.name) / "LINHAI.md"
                        )
                        break

                self.assertTrue(
                    global_memory_found, "GlobalMemory not found in messages"
                )

    def test_priority_order(self):
        """Test that file selection follows the correct priority order."""
        # Create all three files
        with open("LINHAI.md", "w", encoding="utf-8") as f:
            f.write("# LINHAI.md")
        with open("AGENT.md", "w", encoding="utf-8") as f:
            f.write("# AGENT.md")
        with open("CLAUDE.md", "w", encoding="utf-8") as f:
            f.write("# CLAUDE.md")

        mock_config = {
            "llm": {
                "api_key": "test_key",
                "base_url": "http://test.com",
                "model": "test_model",
                "openai_config": {},
                "chat_completion_kwargs": {},
            },
            "agent": {
                "compress_threshold_hard": 52428,
                "compress_threshold_soft": 32768,
                "tool_confirmation": {
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            },
        }

        with patch("linhai.agent.load_config", return_value=mock_config):
            with patch("linhai.agent.OpenAi") as mock_openai:
                mock_openai.return_value = MagicMock()

                agent, _, _, _, _, _ = create_agent()

                # Should select LINHAI.md as highest priority
                global_memory_found = False
                for msg in agent.messages:
                    if isinstance(msg, GlobalMemory):
                        global_memory_found = True
                        self.assertEqual(
                            msg.filepath, Path(self.temp_dir.name) / "LINHAI.md"
                        )
                        break

                self.assertTrue(
                    global_memory_found, "GlobalMemory not found in messages"
                )


if __name__ == "__main__":
    unittest.main()
