"""测试conversation系统。"""

import json
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest import mock

from linhai.registry import Registry
from linhai.agent.conversation import (
    register_conversation_folder,
    save_context,
    save_cleaned_messages,
    save_large_message_chunk,
    save_long_toolcall_output,
    save_secret_intercepted,
)


class TestConversationFunctions(unittest.IsolatedAsyncioTestCase):
    """测试conversation模块的函数。"""

    def setUp(self):
        """测试前准备。"""
        self.temp_dir = tempfile.mkdtemp()
        self.home_patcher = mock.patch(
            "linhai.agent.conversation.Path.home", return_value=Path(self.temp_dir)
        )
        self.home_patcher.start()

        # 创建Registry并注册conversation_folder
        self.registry = Registry()
        self.conversation_dir = register_conversation_folder(self.registry)

    def tearDown(self):
        """测试后清理。"""
        self.home_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_register_conversation_folder(self):
        """测试注册conversation_folder。"""
        # 检查目录是否创建
        self.assertTrue(self.conversation_dir.exists())
        self.assertTrue((self.conversation_dir / "cleaned_messages").exists())
        self.assertTrue((self.conversation_dir / "large_messages").exists())
        self.assertTrue((self.conversation_dir / "long_toolcall").exists())
        self.assertTrue((self.conversation_dir / "secret_intercepted").exists())

        # 检查是否注册到registry
        from pathlib import Path

        retrieved_dir = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        self.assertEqual(retrieved_dir, self.conversation_dir)

    def test_save_cleaned_messages(self):
        """测试保存被清理的消息。"""
        # 创建模拟消息
        mock_msg = mock.Mock()
        mock_msg.to_json.return_value = '{"role": "user", "content": "Test message"}'
        mock_msg.__class__.__name__ = "UserMessage"

        messages = [mock_msg]

        # 保存被清理的消息
        saved_path = save_cleaned_messages(
            self.conversation_dir, messages, prefix="test"
        )

        # 验证文件是否存在
        self.assertTrue(Path(saved_path).exists())

        # 验证文件内容
        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["type"], "UserMessage")
            self.assertEqual(
                data[0]["data"], '{"role": "user", "content": "Test message"}'
            )

    def test_save_large_message_chunk(self):
        """测试保存大消息分块。"""
        content = "This is a large message chunk."
        chunk_index = 0

        saved_path = save_large_message_chunk(
            self.conversation_dir, content, chunk_index
        )

        # 验证文件是否存在
        self.assertTrue(Path(saved_path).exists())

        # 验证文件内容
        with open(saved_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_save_long_toolcall_output(self):
        """测试保存大工具输出。"""
        content = "This is a long tool output."
        tool_name = "test_tool"

        # 测试不分块
        saved_path = save_long_toolcall_output(
            self.conversation_dir, content, tool_name
        )
        self.assertTrue(Path(saved_path).exists())
        with open(saved_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

        # 测试分块
        saved_path_part = save_long_toolcall_output(
            self.conversation_dir, content, tool_name, part_index=1
        )
        self.assertTrue(Path(saved_path_part).exists())
        self.assertIn("part1", str(saved_path_part))

    def test_save_secret_intercepted(self):
        """测试保存被拦截的含secret内容。"""
        content = "This content contains secret."
        tool_name = "test_tool"

        saved_path = save_secret_intercepted(self.conversation_dir, content, tool_name)

        # 验证文件是否存在
        self.assertTrue(Path(saved_path).exists())

        # 验证文件内容
        with open(saved_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)


class TestConversationDirectoryStructure(unittest.TestCase):
    """测试对话目录结构。"""

    def setUp(self):
        """测试前准备。"""
        self.temp_dir = tempfile.mkdtemp()
        self.home_patcher = mock.patch(
            "linhai.agent.conversation.Path.home", return_value=Path(self.temp_dir)
        )
        self.home_patcher.start()

    def tearDown(self):
        """测试后清理。"""
        self.home_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_conversation_dir_path(self):
        """测试对话目录路径是否正确。"""
        registry = Registry()
        conversation_dir = register_conversation_folder(registry)

        # 验证路径包含 ~/.local/share/linhai/conversation/
        expected_base = (
            Path(self.temp_dir) / ".local" / "share" / "linhai" / "conversation"
        )
        self.assertTrue(str(conversation_dir).startswith(str(expected_base)))
