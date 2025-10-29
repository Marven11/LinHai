#!/usr/bin/env python3
"""测试消息类的JSON序列化功能"""

import unittest
from unittest.mock import Mock

from linhai.llm import (
    SystemMessage,
    ChatMessage,
    ToolCallMessage,
    ToolConfirmationMessage,
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
            current_time="2025-10-26 17:00:00",
            group_chat=self.mock_group_chat,
        )
        json_str = original.to_json()
        restored = SystemMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.template, restored.template)
        self.assertEqual(original.current_time, restored.current_time)
        # 不比较to_llm_message()，因为它依赖mock对象且涉及JSON序列化

    def test_chat_message_serialization(self):
        """测试ChatMessage的序列化"""
        original = ChatMessage("user", "这是一条用户消息", "test_user")
        json_str = original.to_json()
        restored = ChatMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.role, restored.role)
        self.assertEqual(original.message, restored.message)
        self.assertEqual(original.name, restored.name)

    def test_tool_call_message_serialization(self):
        """测试ToolCallMessage的序列化"""
        original = ToolCallMessage("test_function", {"arg1": "value1"})
        json_str = original.to_json()
        restored = ToolCallMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.function_name, restored.function_name)
        self.assertEqual(original.function_arguments, restored.function_arguments)

    def test_tool_confirmation_message_serialization(self):
        """测试ToolConfirmationMessage的序列化"""
        tool_call = ToolCallMessage("test_function", {"arg1": "value1"})
        original = ToolConfirmationMessage(tool_call, True)
        json_str = original.to_json()
        restored = ToolConfirmationMessage.from_json(json_str, self.mock_group_chat)

        self.assertEqual(original.confirmed, restored.confirmed)
        self.assertEqual(
            original.tool_call.function_name, restored.tool_call.function_name
        )

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
