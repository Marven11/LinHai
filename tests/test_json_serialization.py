"""测试消息类的JSON序列化功能"""

import unittest
from unittest.mock import Mock

from linhai.llm import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
)
from linhai.tool.main import ToolResultMessage, ToolErrorMessage


class TestJsonSerialization(unittest.TestCase):
    """测试JSON序列化功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_group_chat = Mock()

    def test_system_message_serialization(self):
        """测试SystemMessage的序列化"""
        original = SystemMessage(
            template="这是一条系统消息",
            group_chat=self.mock_group_chat,
        )
        json_str = original.to_json()
        restored = SystemMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.template, restored.template)

    def test_user_message_serialization(self):
        """测试UserMessage的序列化"""
        original = UserMessage("这是一条用户消息", "test_user")
        json_str = original.to_json()
        restored = UserMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.message, restored.message)
        self.assertEqual(original.name, restored.name)

    def test_tool_result_message_serialization(self):
        """测试ToolResultMessage的序列化"""
        original = ToolResultMessage("工具执行结果")
        json_str = original.to_json()
        restored = ToolResultMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.content, restored.content)

    def test_tool_error_message_serialization(self):
        """测试ToolErrorMessage的序列化"""
        original = ToolErrorMessage("工具执行错误")
        json_str = original.to_json()
        restored = ToolErrorMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.content, restored.content)
