"""测试secret拦截保存文件功能"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from linhai.secret import SecretInterceptorPlugin, SecretInfo
from linhai.agent.base import RuntimeMessage


class TestSecretInterceptorPluginWithFileSaving(unittest.TestCase):
    """测试SecretInterceptorPlugin的文件保存功能"""

    def setUp(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 模拟secrets_dict
        self.secrets_dict: dict[str, SecretInfo] = {
            "DEEPSEEK_API_KEY": {"value": "sk-real-123456", "description": "DeepSeek API key"},
            "SSH_PASSWORD": {"value": "mypassword123", "description": "SSH password"},
        }
        
        # 模拟GroupChat
        self.mock_group_chat = Mock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch("linhai.secret.get_current_conversation")
    @patch("linhai.secret.time.time")
    def test_on_tool_result_saves_content_to_file_when_secret_detected_without_with_secret(self, mock_time, mock_get_conversation):
        """测试当结果包含secret值但没有with_secret时，内容被保存到文件"""
        # 模拟固定时间戳
        mock_time.return_value = 1234567890
        
        # 模拟对话管理器
        mock_conversation = Mock()
        mock_conversation_dir = Path(self.temp_dir) / "conversation"
        mock_conversation_dir.mkdir(parents=True, exist_ok=True)
        mock_conversation.conversation_dir = mock_conversation_dir
        mock_get_conversation.return_value = mock_conversation
        
        # 创建插件
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 模拟工具调用结果包含secret值
        result_content = "API key is sk-real-123456 and password is mypassword123"
        
        # 运行异步测试
        async def run_test():
            return await plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                result_content=result_content,
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        
        result = asyncio.run(run_test())
        
        # 验证get_current_conversation被调用
        mock_get_conversation.assert_called_once()
        
        # 验证文件被写入
        expected_filename = "secret_intercepted_1234567890_read_file.txt"
        expected_filepath = mock_conversation_dir / expected_filename
        self.assertTrue(expected_filepath.exists())
        
        # 验证文件内容
        saved_content = expected_filepath.read_text(encoding="utf-8")
        self.assertEqual(saved_content, result_content)
        
        # 验证返回的是RuntimeMessage
        self.assertIsInstance(result, RuntimeMessage)
        result_str = str(result)
        self.assertIn("已拦截", result_str)
        self.assertIn(str(expected_filepath), result_str)
        self.assertIn("DEEPSEEK_API_KEY", result_str)
        self.assertIn("SSH_PASSWORD", result_str)

    @patch("linhai.secret.get_current_conversation")
    def test_on_tool_result_with_secret_specified_masks_content(self, mock_get_conversation):
        """测试当指定了with_secret时，进行掩码但不保存文件"""
        # 创建插件
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 模拟工具调用结果包含secret值，但指定了with_secret
        result_content = "API key is sk-real-123456"
        
        # 运行异步测试
        async def run_test():
            return await plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                result_content=result_content,
                toolcall_arguments=None,
                with_secret=["DEEPSEEK_API_KEY"],
                is_tool_failed_duplicated_error=False,
            )
        
        result = asyncio.run(run_test())
        
        # 验证没有调用get_current_conversation
        mock_get_conversation.assert_not_called()
        
        # 验证返回RuntimeMessage且包含掩码内容
        self.assertIsInstance(result, RuntimeMessage)
        result_str = str(result)
        self.assertIn("已替换", result_str)
        self.assertIn("<$DEEPSEEK_API_KEY$>", result_str)

    @patch("linhai.secret.get_current_conversation")
    def test_on_tool_result_without_secret_returns_none(self, mock_get_conversation):
        """测试当结果不包含secret值时返回None"""
        # 创建插件
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 模拟工具调用结果不包含secret值
        result_content = "This is a normal message without secrets"
        
        # 运行异步测试
        async def run_test():
            return await plugin.on_tool_result(
                tool_name="read_file",
                tool_index=0,
                status="success",
                result_content=result_content,
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        
        result = asyncio.run(run_test())
        
        # 验证没有调用get_current_conversation
        mock_get_conversation.assert_not_called()
        
        # 验证返回None
        self.assertIsNone(result)

    @patch("linhai.secret.get_current_conversation")
    @patch("linhai.secret.time.time")
    def test_on_tool_result_saves_file_with_correct_name_format(self, mock_time, mock_get_conversation):
        """测试保存的文件名格式正确"""
        # 模拟固定时间戳
        mock_time.return_value = 1700000000
        
        # 模拟对话管理器
        mock_conversation = Mock()
        mock_conversation_dir = Path(self.temp_dir) / "conversation"
        mock_conversation_dir.mkdir(parents=True, exist_ok=True)
        mock_conversation.conversation_dir = mock_conversation_dir
        mock_get_conversation.return_value = mock_conversation
        
        # 创建插件
        plugin = SecretInterceptorPlugin(self.mock_group_chat, self.secrets_dict)
        
        # 模拟工具调用
        result_content = "API key is sk-real-123456"
        
        async def run_test():
            return await plugin.on_tool_result(
                tool_name="write_file",
                tool_index=1,
                status="success",
                result_content=result_content,
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        
        result = asyncio.run(run_test())
        
        # 验证文件名格式
        expected_filename = "secret_intercepted_1700000000_write_file.txt"
        expected_filepath = mock_conversation_dir / expected_filename
        self.assertTrue(expected_filepath.exists())
        
        # 验证文件内容
        saved_content = expected_filepath.read_text(encoding="utf-8")
        self.assertEqual(saved_content, result_content)


if __name__ == "__main__":
    unittest.main()
