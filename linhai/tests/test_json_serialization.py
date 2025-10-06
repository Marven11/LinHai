#!/usr/bin/env python3
"""测试消息类的JSON序列化功能"""

import unittest
import json
import sys
import os

from linhai.llm import SystemMessage, ChatMessage, ToolCallMessage, ToolConfirmationMessage
from linhai.tool.main import ToolResultMessage, ToolErrorMessage
from linhai.agent import CheapLlmStatusMessage
from linhai.agent_base import CompressRangeRequest, RuntimeMessage, DestroyedRuntimeMessage, GlobalMemory
from pathlib import Path


class TestJsonSerialization(unittest.TestCase):
    """测试JSON序列化功能"""

    def test_system_message_serialization(self):
        """测试SystemMessage的序列化"""
        original = SystemMessage("这是一条系统消息")
        json_str = original.to_json()
        restored = SystemMessage.from_json(json_str)
        
        self.assertEqual(original.message, restored.message)
        self.assertEqual(original.to_llm_message(), restored.to_llm_message())

    def test_chat_message_serialization(self):
        """测试ChatMessage的序列化"""
        original = ChatMessage("user", "这是一条用户消息", "test_user")
        json_str = original.to_json()
        restored = ChatMessage.from_json(json_str)
        
        self.assertEqual(original.role, restored.role)
        self.assertEqual(original.message, restored.message)
        self.assertEqual(original.name, restored.name)

    def test_tool_call_message_serialization(self):
        """测试ToolCallMessage的序列化"""
        original = ToolCallMessage("test_function", {"arg1": "value1"})
        json_str = original.to_json()
        restored = ToolCallMessage.from_json(json_str)
        
        self.assertEqual(original.function_name, restored.function_name)
        self.assertEqual(original.function_arguments, restored.function_arguments)

    def test_tool_confirmation_message_serialization(self):
        """测试ToolConfirmationMessage的序列化"""
        tool_call = ToolCallMessage("test_function", {"arg1": "value1"})
        original = ToolConfirmationMessage(tool_call, True)
        json_str = original.to_json()
        restored = ToolConfirmationMessage.from_json(json_str)
        
        self.assertEqual(original.confirmed, restored.confirmed)
        self.assertEqual(original.tool_call.function_name, restored.tool_call.function_name)

    def test_tool_result_message_serialization(self):
        """测试ToolResultMessage的序列化"""
        original = ToolResultMessage("工具执行结果")
        json_str = original.to_json()
        restored = ToolResultMessage.from_json(json_str)
        
        self.assertEqual(original.content, restored.content)

    def test_tool_error_message_serialization(self):
        """测试ToolErrorMessage的序列化"""
        original = ToolErrorMessage("工具执行错误")
        json_str = original.to_json()
        restored = ToolErrorMessage.from_json(json_str)
        
        self.assertEqual(original.content, restored.content)

    def test_cheap_llm_status_message_serialization(self):
        """测试CheapLlmStatusMessage的序列化"""
        original = CheapLlmStatusMessage(True)
        json_str = original.to_json()
        restored = CheapLlmStatusMessage.from_json(json_str)
        
        self.assertEqual(original.is_cheap_llm_available, restored.is_cheap_llm_available)

    def test_compress_range_request_serialization(self):
        """测试CompressRangeRequest的序列化"""
        original = CompressRangeRequest("测试总结", 10)
        json_str = original.to_json()
        restored = CompressRangeRequest.from_json(json_str)
        
        self.assertEqual(original.messages_summerization, restored.messages_summerization)
        self.assertEqual(original.message_length, restored.message_length)

    def test_runtime_message_serialization(self):
        """测试RuntimeMessage的序列化"""
        original = RuntimeMessage("运行时消息")
        json_str = original.to_json()
        restored = RuntimeMessage.from_json(json_str)
        
        self.assertEqual(original.message, restored.message)

    def test_destroyed_runtime_message_serialization(self):
        """测试DestroyedRuntimeMessage的序列化"""
        original = DestroyedRuntimeMessage()
        json_str = original.to_json()
        restored = DestroyedRuntimeMessage.from_json(json_str)
        
        # 这个类没有属性，只需要确保可以序列化和反序列化
        self.assertIsInstance(restored, DestroyedRuntimeMessage)

    def test_global_memory_serialization(self):
        """测试GlobalMemory的序列化"""
        original = GlobalMemory(Path("./LINHAI.md"))
        json_str = original.to_json()
        restored = GlobalMemory.from_json(json_str)
        
        self.assertEqual(str(original.filepath), str(restored.filepath))

    def test_json_round_trip(self):
        """测试所有消息类的完整JSON往返"""
        messages = [
            SystemMessage("系统消息"),
            ChatMessage("user", "用户消息"),
            ToolCallMessage("test", {"key": "value"}),
            ToolResultMessage("结果"),
            ToolErrorMessage("错误"),
            CheapLlmStatusMessage(False),
            CompressRangeRequest("总结", 5),
            RuntimeMessage("运行时"),
            DestroyedRuntimeMessage(),
            GlobalMemory(Path("./test.md"))
        ]
        
        for original in messages:
            with self.subTest(msg_type=type(original).__name__):
                json_str = original.to_json()
                # 验证JSON是有效的
                parsed = json.loads(json_str)
                self.assertIsInstance(parsed, (dict, str))
                
                # 验证可以反序列化
                restored = type(original).from_json(json_str)
                self.assertIsInstance(restored, type(original))


if __name__ == "__main__":
    unittest.main()