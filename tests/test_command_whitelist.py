"""
Test command whitelist functionality.
"""

import unittest
from unittest.mock import Mock
from linhai.config import Config
from linhai.agent.plugin import CommandWhitelistPlugin
from linhai.tool.base import ToolResultFailed


class TestCommandWhitelistConfig(unittest.TestCase):
    def test_config_with_allowed_commands(self):
        config_data = {
            "llm": [
                {
                    "name": "test",
                    "base_url": "https://example.com",
                    "api_key": "key",
                    "model": "model",
                }
            ],
            "agent": {
                "allowed_commands": [
                    ["ls"],
                    ["git", "status"],
                ]
            }
        }
        config = Config(**config_data)
        self.assertEqual(len(config.agent.allowed_commands), 2)
        self.assertEqual(config.agent.allowed_commands[0], ["ls"])
        self.assertEqual(config.agent.allowed_commands[1], ["git", "status"])

    def test_config_without_allowed_commands(self):
        config_data = {
            "llm": [
                {
                    "name": "test",
                    "base_url": "https://example.com",
                    "api_key": "key",
                    "model": "model",
                }
            ],
        }
        config = Config(**config_data)
        self.assertEqual(config.agent.allowed_commands, [])


class TestCommandWhitelistPlugin(unittest.IsolatedAsyncioTestCase):
    async def test_plugin_allows_whitelisted_command(self):
        config = Mock()
        config.agent = Mock()
        config.agent.allowed_commands = [["ls"]]
        group_chat = Mock()
        plugin = CommandWhitelistPlugin(group_chat, config)
        
        agent = Mock()
        context = {}
        
        result = await plugin.before_tool_call(
            "process_create",
            0,
            {"command": ["ls", "-lah"]},
            None,
            agent,
            context,
        )
        self.assertIsNone(result)

    async def test_plugin_blocks_non_whitelisted_command(self):
        config = Mock()
        config.agent = Mock()
        config.agent.allowed_commands = [["ls"]]
        group_chat = Mock()
        plugin = CommandWhitelistPlugin(group_chat, config)
        
        agent = Mock()
        context = {}
        
        result = await plugin.before_tool_call(
            "process_create",
            0,
            {"command": ["git", "commit"]},
            None,
            agent,
            context,
        )
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("不在白名单中", result.content)

    async def test_plugin_ignores_other_tools(self):
        config = Mock()
        config.agent = Mock()
        config.agent.allowed_commands = [["ls"]]
        group_chat = Mock()
        plugin = CommandWhitelistPlugin(group_chat, config)
        
        agent = Mock()
        context = {}
        
        result = await plugin.before_tool_call(
            "read_file",
            0,
            {"filepath": "test.txt"},
            None,
            agent,
            context,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
