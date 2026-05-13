"""测试消息类的JSON序列化功能"""

import json
import unittest
from unittest.mock import Mock

from linhai.base import SystemMessage, UserMessage, AssistantMessage
from linhai.tool.base import (
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
)


class TestJsonSerialization(unittest.TestCase):
    """测试JSON序列化功能"""

    def setUp(self):
        """设置测试环境"""
        from linhai.tool.main import ToolManager
        from unittest.mock import Mock

        self.mock_registry = Mock()
        # 为SystemMessage初始化提供mock的tool_manager
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "tool_manager":
                return mock_tool_manager
            raise RuntimeError(f"{member_type!r} not exists")

        self.mock_registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

    def test_system_message_serialization(self):
        """测试SystemMessage的序列化"""
        original = SystemMessage(
            registry=self.mock_registry,
        )
        json_str = original.to_json()
        restored = SystemMessage.from_json(json_str, self.mock_registry)

        # 验证反序列化后的对象也是SystemMessage实例
        self.assertIsInstance(restored, SystemMessage)

        # 比较序列化前后的JSON数据（忽略可能的额外字段）
        original_data = json.loads(json_str)
        restored_data = json.loads(restored.to_json())

        # SystemMessage的JSON包含结构化数据，验证关键字段存在
        self.assertIn("overview", original_data)
        self.assertIn("overview", restored_data)

        # 确保registry正确传递（虽然不被序列化，但from_json会传入）
        # 我们无法直接比较registry，但可以确认它们都使用相同的mock_registry
        # 通过检查to_llm_message()返回相同内容来间接验证
        original_llm_msg = original.to_llm_message()
        restored_llm_msg = restored.to_llm_message()

        # 比较LLM消息的role和content
        self.assertEqual(original_llm_msg.get("role"), restored_llm_msg.get("role"))
        self.assertEqual(
            original_llm_msg.get("content"), restored_llm_msg.get("content")
        )

    def test_user_message_serialization(self):
        """测试UserMessage的序列化"""
        original = UserMessage("这是一条用户消息", "test_user")
        json_str = original.to_json()
        restored = UserMessage.from_json(json_str, self.mock_registry)

        self.assertEqual(original.message, restored.message)
        # name字段不再序列化，所以不检查name字段

    def test_tool_result_message_serialization(self):
        """测试ToolResultMessage的序列化"""
        original = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=0,
            result=SuccessfulToolResult(content="工具执行结果"),
            toolcall_arguments=None,
        )
        json_str = original.to_json()
        restored = ToolCallResultMessage.from_json(json_str, self.mock_registry)

        self.assertEqual(original.result.content, restored.result.content)
        self.assertEqual(original.tool_name, restored.tool_name)

    def test_tool_error_message_serialization(self):
        """测试ToolErrorMessage的序列化"""
        original = ToolCallResultMessage(
            tool_name="test_tool",
            tool_index=0,
            result=FailedToolResult(content="工具执行错误"),
            toolcall_arguments={"arg": "value"},
        )
        json_str = original.to_json()
        restored = ToolCallResultMessage.from_json(json_str, self.mock_registry)

        self.assertEqual(original.result.content, restored.result.content)
        self.assertEqual(original.tool_name, restored.tool_name)

    def test_unicode_preservation(self):
        chinese_text = "保存json时保留unicode中文测试"

        user_msg = UserMessage(chinese_text)
        json_str = user_msg.to_json()
        self.assertIn(chinese_text, json_str)
        self.assertNotIn("\\u", json_str)

        assistant_msg = AssistantMessage(chinese_text)
        json_str = assistant_msg.to_json()
        self.assertIn(chinese_text, json_str)
        self.assertNotIn("\\u", json_str)

        success_result = SuccessfulToolResult(content=chinese_text)
        json_str = success_result.to_json()
        self.assertIn(chinese_text, json_str)
        self.assertNotIn("\\u", json_str)

        failed_result = FailedToolResult(content=chinese_text)
        json_str = failed_result.to_json()
        self.assertIn(chinese_text, json_str)
        self.assertNotIn("\\u", json_str)
