"""测试create_agent函数中的MCP配置功能"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
import tempfile
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.group_chat import GroupChat
from linhai.agent import create_agent


class TestCreateAgentMCP(unittest.TestCase):
    """测试create_agent函数中的MCP配置功能"""

    def setUp(self):
        """设置测试fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.group_chat = GroupChat()

    def tearDown(self):
        """清理测试fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        """创建临时配置文件"""
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    @patch('linhai.agent.MCPConnector')
    @patch('os.path.exists')
    def test_create_agent_with_mcp_config(self, mock_exists, mock_mcp_connector_class):
        """测试create_agent函数正确配置MCP服务器"""
        # 模拟文件存在
        mock_exists.return_value = True
        
        # 创建包含MCP配置的测试配置文件
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold_soft = 40000
compress_threshold_hard = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "mcp_server_example.py"

[[agent.mcp]]
name = "another_server"
server_script_path = "another_server.py"
"""
        config_path = self.create_test_config(config_content)
        
        # 模拟MCPConnector实例，完全mock连接过程
        mock_connector_instance = AsyncMock()
        mock_mcp_connector_class.return_value = mock_connector_instance
        
        # Mock connect_stdio方法，避免实际连接
        mock_connector_instance.connect_stdio = AsyncMock()
        
        # 调用create_agent
        result = asyncio.run(create_agent(self.group_chat, config_path))
        
        # 验证结果 - create_agent返回的是Agent对象
        from linhai.agent import Agent
        self.assertIsInstance(result, Agent)
        
        # 验证MCPConnector被创建
        mock_mcp_connector_class.assert_called_once_with(self.group_chat)
        
        # 验证connect_stdio被调用了两次（对应两个MCP服务器）
        self.assertEqual(mock_connector_instance.connect_stdio.call_count, 2)
        
        # 验证第一个MCP服务器的连接参数
        first_call_args = mock_connector_instance.connect_stdio.call_args_list[0]
        self.assertEqual(first_call_args[0][0], "calculator")  # name
        self.assertTrue(first_call_args[0][1].endswith("mcp_server_example.py"))  # server_script_path
        
        # 验证第二个MCP服务器的连接参数
        second_call_args = mock_connector_instance.connect_stdio.call_args_list[1]
        self.assertEqual(second_call_args[0][0], "another_server")  # name
        self.assertTrue(second_call_args[0][1].endswith("another_server.py"))  # server_script_path

    def test_create_agent_without_mcp_config(self):
        """测试没有MCP配置时create_agent函数正常工作"""
        # 创建不包含MCP配置的测试配置文件
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold_soft = 40000
compress_threshold_hard = 80000
"""
        config_path = self.create_test_config(config_content)
        
        # 调用create_agent
        result = asyncio.run(create_agent(self.group_chat, config_path))
        
        # 验证结果 - create_agent返回的是Agent对象
        from linhai.agent import Agent
        self.assertIsInstance(result, Agent)
        
        # 检查group_chat中是否注册了agent成员
        agent = self.group_chat.get_members("agent", Agent)
        self.assertIsNotNone(agent)

    @patch('linhai.agent.MCPConnector')
    @patch('os.path.exists')
    def test_create_agent_with_mcp_relative_path_conversion(self, mock_exists, mock_mcp_connector_class):
        """测试MCP相对路径转换为绝对路径"""
        # 模拟文件存在
        mock_exists.return_value = True
        
        # 创建包含相对路径MCP配置的测试配置文件
        config_content = """
[[llm]]
name = "test"
base_url = "https://example.com"
api_key = "test-key"
model = "test-model"

[agent]
compress_threshold_soft = 40000
compress_threshold_hard = 80000

[[agent.mcp]]
name = "calculator"
server_script_path = "../mcp_server_example.py"
"""
        config_path = self.create_test_config(config_content)
        
        # 模拟MCPConnector实例，完全mock连接过程
        mock_connector_instance = AsyncMock()
        mock_mcp_connector_class.return_value = mock_connector_instance
        
        # Mock connect_stdio方法，避免实际连接
        mock_connector_instance.connect_stdio = AsyncMock()
        
        # 调用create_agent
        asyncio.run(create_agent(self.group_chat, config_path))
        
        # 验证connect_stdio被调用，且路径是绝对路径
        mock_connector_instance.connect_stdio.assert_called_once()
        call_args = mock_connector_instance.connect_stdio.call_args[0]
        server_script_path = call_args[1]
        
        # 验证路径是绝对路径
        self.assertTrue(os.path.isabs(server_script_path))
        # 验证路径正确转换
        expected_path = str(config_path.parent.parent / "mcp_server_example.py")
        self.assertEqual(os.path.normpath(server_script_path), os.path.normpath(expected_path))


if __name__ == "__main__":
    unittest.main()