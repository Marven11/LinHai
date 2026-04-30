"""
Test command whitelist functionality.
"""

import unittest
from unittest.mock import Mock
from linhai.config import Config
from linhai.plugin import CommandWhitelistPlugin
from linhai.tool.base import FailedToolResult


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
            "agent": [
                {
                    "allowed_commands": [
                        ["ls"],
                        ["git", "status"],
                    ]
                }
            ],
        }
        config = Config(**config_data)
        self.assertEqual(len(config.agent[0].allowed_commands), 2)
        self.assertEqual(config.agent[0].allowed_commands[0], ["ls"])
        self.assertEqual(config.agent[0].allowed_commands[1], ["git", "status"])

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
        self.assertEqual(len(config.agent), 0)


class TestCommandWhitelistPlugin(unittest.IsolatedAsyncioTestCase):
    async def test_plugin_allows_whitelisted_command(self):
        allowed_commands = [["ls"]]
        registry = Mock()
        plugin = CommandWhitelistPlugin(registry, allowed_commands)

        agent = Mock()
        context = {}

        result = await plugin.before_tool_call(
            "process_create",
            {"argv": ["ls", "-lah"]},
            None,
        )
        self.assertIsNone(result)

    async def test_plugin_blocks_non_whitelisted_command(self):
        allowed_commands = [["ls"]]
        registry = Mock()
        plugin = CommandWhitelistPlugin(registry, allowed_commands)

        agent = Mock()
        context = {}

        result = await plugin.before_tool_call(
            "process_create",
            {"argv": ["git", "commit"]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("不在白名单中", result.content)

    async def test_plugin_ignores_other_tools(self):
        allowed_commands = [["ls"]]
        registry = Mock()
        plugin = CommandWhitelistPlugin(registry, allowed_commands)

        agent = Mock()
        context = {}

        result = await plugin.before_tool_call(
            "read_file",
            {"filepath": "test.txt"},
            None,
        )
        self.assertIsNone(result)

    async def test_plugin_rejects_non_list_argv(self):
        """测试argv不是列表类型时返回错误"""
        allowed_commands = [["ls"]]
        registry = Mock()
        plugin = CommandWhitelistPlugin(registry, allowed_commands)

        # argv是字符串
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": "ls -lah"},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

        # argv是数字
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": 123},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

        # argv是字典
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": {"command": "ls"}},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是列表类型", result.content)

    async def test_plugin_rejects_non_string_elements(self):
        """测试argv包含非字符串元素时返回错误"""
        allowed_commands = [["ls"]]
        registry = Mock()
        plugin = CommandWhitelistPlugin(registry, allowed_commands)

        # argv包含数字
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": ["ls", 123, "-lah"]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)
        self.assertIn("第1个元素", result.content)  # 索引从0开始，123是第1个元素

        # argv包含列表
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": ["ls", ["-l", "-a"], "-h"]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)

        # argv包含字典
        result = await plugin.before_tool_call(
            "process_create",
            {"argv": ["ls", {"option": "-l"}, "-a"]},
            None,
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("必须是字符串类型", result.content)


if __name__ == "__main__":
    unittest.main()
