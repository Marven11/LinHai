"""Unit tests for global memory file path selection."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import os
import asyncio

from linhai.agent import create_agent
from linhai.agent.base import GlobalMemory
from linhai.config import Config, LLMConfig, AgentConfig


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
        # Mock file existence and content
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pathlib.Path.open") as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "# Test LINHAI.md\nTest content"

                mock_llm_config = LLMConfig(
                    name="test_llm",
                    api_key="test_key",
                    base_url="http://test.com",
                    model="test_model",
                )
                mock_agent_config = AgentConfig(
                    compress_threshold_hard=60000,
                    compress_threshold_soft=30000,
                    tool_confirmation={
                        "skip_confirmation": True,
                        "whitelist": [],
                    },
                )
                mock_config = Config(llm=[mock_llm_config], agent=mock_agent_config)

                # Mock the entire config loading process
                with patch("linhai.config.load_config", return_value=mock_config):
                    with patch("linhai.llm.OpenAi") as mock_openai:
                        mock_openai.return_value = MagicMock()

                        group_chat = MagicMock()
                        # Use a mock config path that doesn't need to exist
                        asyncio.run(create_agent(group_chat, "/dev/null/test_config.toml"))
                        # 从 group_chat 获取 agent 实例
                        agent = MagicMock()
                        agent.messages = []
                        group_chat.get_members.return_value = [agent]

                        # Check if GlobalMemory is in messages
                        global_memory_found = False
                        for msg in agent.messages:
                            if isinstance(msg, GlobalMemory):
                                global_memory_found = True
                                break

                        self.assertTrue(
                            global_memory_found, "GlobalMemory not found in messages"
                        )

    def test_agent_md_in_current_directory(self):
        """Test that AGENT.md in current directory is selected when LINHAI.md is missing."""
        # Mock file existence - only AGENT.md exists
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = lambda path: path.name == "AGENT.md"
            with patch("pathlib.Path.open") as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "# Test AGENT.md\nTest content"

                mock_llm_config = LLMConfig(
                    name="test_llm",
                    api_key="test_key",
                    base_url="http://test.com",
                    model="test_model",
                )
                mock_agent_config = AgentConfig(
                    compress_threshold_hard=60000,
                    compress_threshold_soft=30000,
                    tool_confirmation={
                        "skip_confirmation": True,
                        "whitelist": [],
                    },
                )
                mock_config = Config(llm=[mock_llm_config], agent=mock_agent_config)

                # Mock the entire config loading process
                with patch("linhai.config.load_config", return_value=mock_config):
                    with patch("linhai.llm.OpenAi") as mock_openai:
                        mock_openai.return_value = MagicMock()

                        group_chat = MagicMock()
                        # Use a mock config path that doesn't need to exist
                        asyncio.run(create_agent(group_chat, "/dev/null/test_config.toml"))
                        # 从 group_chat 获取 agent 实例
                        agent = MagicMock()
                        agent.messages = []
                        group_chat.get_members.return_value = [agent]

                        # Check if GlobalMemory is in messages
                        global_memory_found = False
                        for msg in agent.messages:
                            if isinstance(msg, GlobalMemory):
                                global_memory_found = True
                                break

                        self.assertTrue(
                            global_memory_found, "GlobalMemory not found in messages"
                        )

    def test_no_files_in_current_directory(self):
        """Test behavior when no memory files exist in current directory."""
        # Mock no files exist
        with patch("pathlib.Path.exists", return_value=False):
            mock_llm_config = LLMConfig(
                name="test_llm",
                api_key="test_key",
                base_url="http://test.com",
                model="test_model",
            )
            mock_agent_config = AgentConfig(
                compress_threshold_hard=60000,
                compress_threshold_soft=30000,
                tool_confirmation={
                    "skip_confirmation": True,
                    "whitelist": [],
                },
            )
            mock_config = Config(llm=[mock_llm_config], agent=mock_agent_config)

            # Mock the entire config loading process
            with patch("linhai.config.load_config", return_value=mock_config):
                with patch("linhai.llm.OpenAi") as mock_openai:
                    mock_openai.return_value = MagicMock()

                    group_chat = MagicMock()
                    # Use a mock config path that doesn't need to exist
                    asyncio.run(create_agent(group_chat, "/dev/null/test_config.toml"))
                    # 从 group_chat 获取 agent 实例
                    agent = MagicMock()
                    agent.messages = []
                    group_chat.get_members.return_value = [agent]

                    # Check if GlobalMemory is still added with default path
                    global_memory_found = False
                    for msg in agent.messages:
                        if isinstance(msg, GlobalMemory):
                            global_memory_found = True
                            break

                    self.assertTrue(
                        global_memory_found, "GlobalMemory not found in messages"
                    )


if __name__ == "__main__":
    unittest.main()