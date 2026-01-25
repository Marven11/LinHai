"""测试conversation系统。"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase, mock

from linhai.group_chat import GroupChat
from linhai.agent.conversation import ConversationManager
from linhai.llm import UserMessage, AssistantMessage


class TestConversationManager(TestCase):
    """测试ConversationManager类。"""

    def setUp(self):
        """测试前准备。"""
        # 创建临时目录作为conversation基础目录
        self.temp_dir = tempfile.mkdtemp()
        self.conversation_id = "test-conversation-123"
        self.base_dir = Path(self.temp_dir) / ".local" / "share" / "conversation"
        
        # 创建GroupChat模拟对象
        self.group_chat_mock = mock.Mock(spec=GroupChat)
        
        # 模拟home目录
        self.home_patcher = mock.patch(
            "linhai.agent.conversation.Path.home",
            return_value=Path(self.temp_dir)
        )
        self.home_patcher.start()
        
        # 创建ConversationManager实例
        self.conv = ConversationManager(self.conversation_id)
    
    def tearDown(self):
        """测试后清理。"""
        self.home_patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_init_conversation(self):
        """测试对话管理器初始化。"""
        # 检查目录是否创建
        expected_dir = self.base_dir / self.conversation_id
        self.assertTrue(expected_dir.exists())
        self.assertTrue((expected_dir / "splited_large_message").exists())
        self.assertTrue((expected_dir / "cleaned_messages").exists())
        
        # 检查conversation_id
        self.assertEqual(self.conv.get_conversation_id(), self.conversation_id)
    
    def test_get_conversation_dir(self):
        """测试获取对话目录路径。"""
        expected_path = self.base_dir / self.conversation_id
        actual_path = ConversationManager.get_conversation_dir(self.conversation_id)
        self.assertEqual(actual_path, expected_path)
    
    def test_save_and_load_context(self):
        """测试保存和加载context.json。"""
        # 模拟消息的to_json方法
        mock_user_msg = mock.Mock()
        mock_user_msg.to_json.return_value = '{"role": "user", "content": "Hello, world!"}'
        mock_user_msg.__class__.__name__ = "UserMessage"
        
        mock_assistant_msg = mock.Mock()
        mock_assistant_msg.to_json.return_value = '{"role": "assistant", "content": "Hi there!"}'
        mock_assistant_msg.__class__.__name__ = "AssistantMessage"
        
        messages = [mock_user_msg, mock_assistant_msg]
        
        # 保存消息
        saved_path = self.conv.save_context(messages)
        self.assertTrue(Path(saved_path).exists())
        
        # 加载消息应该抛出RuntimeError，因为需要GroupChat参数
        with self.assertRaises(RuntimeError) as cm:
            self.conv.load_context()
        
        self.assertIn("需要GroupChat参数", str(cm.exception))
    
    def test_save_cleaned_messages(self):
        """测试保存被清理的消息。"""
        # 模拟消息
        mock_msg = mock.Mock()
        mock_msg.to_json.return_value = '{"role": "user", "content": "Test message"}'
        mock_msg.__class__.__name__ = "UserMessage"
        
        messages = [mock_msg]
        
        # 保存被清理的消息
        saved_path = self.conv.save_cleaned_messages(messages, prefix="test")
        
        # 验证文件是否存在
        self.assertTrue(Path(saved_path).exists())
        
        # 验证文件内容
        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["type"], "UserMessage")
            self.assertEqual(data[0]["data"], '{"role": "user", "content": "Test message"}')
    
    def test_save_large_message_chunk(self):
        """测试保存大消息分块。"""
        content = "This is a large message chunk."
        chunk_index = 0
        
        saved_path = self.conv.save_large_message_chunk(content, chunk_index)
        
        # 验证文件是否存在
        self.assertTrue(Path(saved_path).exists())
        
        # 验证文件内容
        with open(saved_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)
    
    def test_load_context_file_not_found(self):
        """测试加载不存在的context.json文件。"""
        # 删除context.json文件
        context_file = self.conv.conversation_dir / "context.json"
        if context_file.exists():
            context_file.unlink()
        
        # 应该抛出FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.conv.load_context()
    
    def test_init_conversation_no_id(self):
        """测试没有提供conversation_id时生成UUID。"""
        conv = ConversationManager()
        # 验证conversation_id是有效的UUID格式
        import uuid
        try:
            uuid.UUID(conv.get_conversation_id())
        except ValueError:
            self.fail("conversation_id不是有效的UUID")


class TestConversationGlobalFunctions(TestCase):
    """测试conversation模块的全局函数。"""
    
    def setUp(self):
        """测试前准备。"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 模拟home目录
        self.home_patcher = mock.patch(
            "linhai.agent.conversation.Path.home",
            return_value=Path(self.temp_dir)
        )
        self.home_patcher.start()
        
        # 重置全局状态 - 直接操作模块属性
        import linhai.agent.conversation as conv_module
        conv_module._current_conversation = None
    
    def tearDown(self):
        """测试后清理。"""
        self.home_patcher.stop()
        shutil.rmtree(self.temp_dir)
        
        # 重置全局状态 - 直接操作模块属性
        import linhai.agent.conversation as conv_module
        conv_module._current_conversation = None
    
    def test_init_and_get_conversation(self):
        """测试初始化和获取当前对话。"""
        from linhai.agent.conversation import init_conversation, get_current_conversation
        
        # 初始化对话
        conv = init_conversation("test-id")
        self.assertIsNotNone(conv)
        self.assertEqual(conv.get_conversation_id(), "test-id")
        
        # 获取当前对话
        current_conv = get_current_conversation()
        self.assertIs(current_conv, conv)
    
    def test_get_current_conversation_not_initialized(self):
        """测试获取未初始化的当前对话。"""
        from linhai.agent.conversation import get_current_conversation
        import linhai.agent.conversation as conv_module
        
        # 确保全局状态被重置 - 直接操作模块属性
        conv_module._current_conversation = None
        
        with self.assertRaises(RuntimeError) as cm:
            get_current_conversation()
        
        self.assertIn("not initialized", str(cm.exception).lower())
