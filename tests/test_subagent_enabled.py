"""测试SubAgent开关功能。"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import os

from linhai.config import load_config
from linhai.agent.create import create_agent_from_config


class TestSubAgentEnabled(unittest.IsolatedAsyncioTestCase):
    """测试SubAgent开关功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = AsyncMock()
        self.group_chat.register_member = Mock()
        self.group_chat.register_queue = Mock()
        self.group_chat.send_if_exists = AsyncMock()
        self.group_chat.send = AsyncMock()
        self.group_chat.receive = AsyncMock()
        self.group_chat.is_empty = Mock(return_value=True)
        self.group_chat.get_members = Mock()

    def create_test_config(self, subagent_enabled: bool):
        """创建测试配置文件。"""
        config_content = f"""
[[llm]]
name = "test_llm"
base_url = "https://api.example.com/v1"
api_key = "test_key"
model = "test-model"

[subagent]
enable = {str(subagent_enabled).lower()}
default_llm = "test_llm"
"""
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as f:
            f.write(config_content)
        return Path(path)

    async def test_subagent_enabled_true(self):
        """测试SubAgent启用时的情况。"""
        config_path = self.create_test_config(subagent_enabled=True)
        
        try:
            config = load_config(config_path)
            
            # 验证配置加载正确
            self.assertTrue(config.subagent_enabled)
            self.assertIsNotNone(config.subagent)
            assert config.subagent is not None  # 确保pyright知道subagent不为None
            self.assertTrue(config.subagent.enable)
            
            # 验证字符串表示包含enabled信息
            config_str = str(config)
            self.assertIn("subagent_enabled=True", config_str)
            
        finally:
            os.unlink(config_path)

    async def test_subagent_enabled_false(self):
        """测试SubAgent禁用时的情况。"""
        config_path = self.create_test_config(subagent_enabled=False)
        
        try:
            config = load_config(config_path)
            
            # 验证配置加载正确
            self.assertFalse(config.subagent_enabled)
            self.assertIsNotNone(config.subagent)
            assert config.subagent is not None  # 确保pyright知道subagent不为None
            self.assertFalse(config.subagent.enable)
            
            # 验证字符串表示包含enabled信息
            config_str = str(config)
            self.assertIn("subagent_enabled=False", config_str)
            
        finally:
            os.unlink(config_path)

    async def test_subagent_config_none(self):
        """测试没有subagent配置时的情况。"""
        config_content = """
[[llm]]
name = "test_llm"
base_url = "https://api.example.com/v1"
api_key = "test_key"
model = "test-model"
"""
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            # 验证subagent为None
            self.assertIsNone(config.subagent)
            self.assertFalse(config.subagent_enabled)
            
            # 验证字符串表示包含enabled信息
            config_str = str(config)
            self.assertIn("subagent_enabled=False", config_str)
            
        finally:
            os.unlink(path)

    @patch("linhai.agent.create.OpenAi")
    async def test_create_agent_with_subagent_disabled(self, mock_openai):
        """测试创建Agent时SubAgent被禁用的情况。"""
        mock_llm = AsyncMock()
        mock_llm.answer_stream = AsyncMock()
        mock_openai.return_value = mock_llm
        
        config_path = self.create_test_config(subagent_enabled=False)
        
        try:
            # 创建Agent
            config = load_config(config_path)
            agent = await create_agent_from_config(self.group_chat, config, None)
            
            # 验证SubAgent相关组件没有被创建
            # SubAgentManager不应该被注册到group_chat
            subagent_manager_calls = [
                call for call in self.group_chat.register_member.call_args_list
                if call and len(call[0]) > 0 and call[0][0] == "subagent_manager"
            ]
            self.assertEqual(len(subagent_manager_calls), 0)
            
            # 验证SubAgentCollaborationPlugin没有被注册
            # 检查lifecycle的plugins列表
            has_subagent_plugin = any(
                plugin.__class__.__name__ == "SubAgentCollaborationPlugin"
                for plugin in agent.lifecycle._plugins
            )
            self.assertFalse(has_subagent_plugin)
            
        finally:
            os.unlink(config_path)

    @patch("linhai.agent.create.OpenAi")
    async def test_create_agent_with_subagent_enabled(self, mock_openai):
        """测试创建Agent时SubAgent被启用的情况。"""
        mock_llm = AsyncMock()
        mock_llm.answer_stream = AsyncMock()
        mock_openai.return_value = mock_llm
        
        config_path = self.create_test_config(subagent_enabled=True)
        
        try:
            # 创建Agent
            config = load_config(config_path)
            agent = await create_agent_from_config(self.group_chat, config, None)
            
            # 验证SubAgent相关组件被创建
            # SubAgentManager应该被注册到group_chat
            subagent_manager_calls = [
                call for call in self.group_chat.register_member.call_args_list
                if call and len(call[0]) > 0 and call[0][0] == "subagent_manager"
            ]
            self.assertEqual(len(subagent_manager_calls), 1)
            
            # 验证SubAgent相关组件被创建
            subagent_manager_calls = [
                call for call in self.group_chat.register_member.call_args_list
                if call and len(call[0]) > 0 and call[0][0] == "subagent_manager"
            ]
            self.assertEqual(len(subagent_manager_calls), 1)
            
        finally:
            os.unlink(config_path)


if __name__ == "__main__":
    unittest.main()
