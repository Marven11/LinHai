"""测试secret拦截保存文件功能"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from linhai.secret import SecretInterceptorPlugin, SecretInfo
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.agent.messages import RuntimeMessage


class TestSecretInterceptorPluginWithFileSaving(unittest.TestCase):
    """测试SecretInterceptorPlugin的文件保存功能"""

    def setUp(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()

        # 模拟secrets_dict
        self.secrets_dict: dict[str, SecretInfo] = {
            "DEEPSEEK_API_KEY": {
                "value": "sk-real-123456",
                "description": "DeepSeek API key",
            },
            "SSH_PASSWORD": {"value": "mypassword123", "description": "SSH password"},
        }

        # 模拟Registry
        self.mock_registry = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_after_toolcall_saves_content_to_file_when_secret_detected_without_with_secret(
        self,
    ):
        """测试当结果包含secret值但没有with_secret时，内容被保存到文件"""
        # 使用真实Registry并注册conversation_folder
        from linhai.registry import Registry
        from linhai.agent.conversation import register_conversation_folder

        real_registry = Registry()
        register_conversation_folder(real_registry)

        # 创建插件使用真实registry
        from linhai.secret import SecretInterceptorPlugin

        plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        # 模拟工具调用结果包含secret值
        result_content = "API key is sk-real-123456 and password is mypassword123"

        # 运行异步测试
        async def run_test():
            return await plugin.after_toolcall(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )

        result = asyncio.run(run_test())

        # 验证返回的是RuntimeMessage
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIsInstance(result.replacement, RuntimeMessage)
        result_str = str(result)
        self.assertIn("secret键的内容", result_str)
        self.assertIn("DEEPSEEK_API_KEY", result_str)
        self.assertIn("SSH_PASSWORD", result_str)

    def test_after_toolcall_with_secret_specified_masks_content(self):
        """测试当指定了with_secret时，进行掩码但不保存文件"""
        # 使用真实Registry并注册conversation_folder
        from linhai.registry import Registry
        from linhai.agent.conversation import register_conversation_folder

        real_registry = Registry()
        register_conversation_folder(real_registry)

        # 创建插件使用真实registry
        plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        # 模拟工具调用结果包含secret值，但指定了with_secret
        result_content = "API key is sk-real-123456"

        # 运行异步测试
        async def run_test():
            return await plugin.after_toolcall(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments=None,
                with_secret={
                    "in_arguments": ["DEEPSEEK_API_KEY"],
                    "in_result": ["DEEPSEEK_API_KEY"],
                },
                is_tool_failed_duplicated_error=False,
            )

        result = asyncio.run(run_test())

        # 验证返回RuntimeMessage且包含掩码内容
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIsInstance(result.replacement, RuntimeMessage)
        result_str = str(result)
        self.assertIn("已替换", result_str)
        self.assertIn("<$DEEPSEEK_API_KEY$>", result_str)

    def test_after_toolcall_without_secret_returns_none(self):
        """测试当结果不包含secret值时返回None"""
        # 使用真实Registry并注册conversation_folder
        from linhai.registry import Registry
        from linhai.agent.conversation import register_conversation_folder

        real_registry = Registry()
        register_conversation_folder(real_registry)

        # 创建插件使用真实registry
        from linhai.secret import SecretInterceptorPlugin

        plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        # 模拟工具调用结果不包含secret值
        result_content = "This is a normal message without secrets"

        # 运行异步测试
        async def run_test():
            return await plugin.after_toolcall(
                tool_name="read_file",
                tool_index=0,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )

        result = asyncio.run(run_test())

        # 验证返回None
        self.assertIsNone(result)

    def test_after_toolcall_saves_file_with_correct_name_format(self):
        """测试保存的文件名格式正确"""
        # 使用真实Registry并注册conversation_folder
        from linhai.registry import Registry
        from linhai.agent.conversation import register_conversation_folder

        real_registry = Registry()
        conversation_dir = register_conversation_folder(real_registry)

        # 创建插件使用真实registry
        from linhai.secret import SecretInterceptorPlugin

        plugin = SecretInterceptorPlugin(real_registry, self.secrets_dict)

        # 模拟工具调用
        result_content = "API key is sk-real-123456"

        async def run_test():
            return await plugin.after_toolcall(
                tool_name="write_file",
                tool_index=1,
                status="success",
                message=RuntimeMessage(result_content),
                toolcall_arguments=None,
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )

        result = asyncio.run(run_test())

        # 验证文件被创建在正确的目录
        secret_dir = conversation_dir / "secret_intercepted"
        self.assertTrue(secret_dir.exists())

        # 验证文件存在且内容正确
        files = list(secret_dir.glob("secret_intercepted_*_write_file.txt"))
        self.assertEqual(len(files), 1)

        # 验证文件内容
        saved_content = files[0].read_text(encoding="utf-8")
        self.assertIn(result_content, saved_content)


if __name__ == "__main__":
    unittest.main()
