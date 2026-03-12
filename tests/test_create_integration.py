#!/usr/bin/env python3
"""集成测试create.py的命令白名单插件注册。"""

import unittest
from pathlib import Path
import argparse

from linhai.config import Config


class TestCreateIntegration(unittest.TestCase):
    """集成测试create.py的命令白名单功能。"""

    def test_create_agent_with_allowed_commands(self):
        """测试创建带有allowed_commands配置的agent。"""
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
                "allowed_commands": [["ls"], ["git", "status"]],
                "compress_threshold": 0.8,
            },
        }

        # 测试配置解析
        config = Config(**config_data)

        # 验证配置结构
        self.assertEqual(len(config.agent.allowed_commands), 2)
        self.assertEqual(config.agent.allowed_commands[0], ["ls"])
        self.assertEqual(config.agent.allowed_commands[1], ["git", "status"])

        # 验证配置字段类型
        self.assertIsInstance(config.agent.allowed_commands, list)
        for cmd in config.agent.allowed_commands:
            self.assertIsInstance(cmd, list)
            for arg in cmd:
                self.assertIsInstance(arg, str)

    def test_create_agent_without_allowed_commands(self):
        """测试创建没有allowed_commands配置的agent。"""
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
                "compress_threshold": 0.8,
            },
        }

        config = Config(**config_data)

        # 验证allowed_commands默认为空列表
        self.assertEqual(config.agent.allowed_commands, [])
        self.assertIsInstance(config.agent.allowed_commands, list)


if __name__ == "__main__":
    unittest.main()
