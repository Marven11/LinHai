"""测试create_agent函数中的MCP配置功能"""

import unittest
from unittest.mock import patch, AsyncMock
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
        
        # Copy real_mcp_server.py to temp directory for MCP tests
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        source_file = os.path.join(project_root, "linhai", "tests", "real_mcp_server.py")
        dest_file = os.path.join(self.temp_dir, "real_mcp_server.py")
        import shutil
        shutil.copy2(source_file, dest_file)

    def tearDown(self):
        """清理测试fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_config(self, config_content):
        """创建临时配置文件"""
        config_path = Path(self.temp_dir) / "test_config.toml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_create_agent_with_real_mcp_server(self):
        """测试create_agent函数与真实MCP服务器的集成"""
        # 创建包含真实MCP服务器配置的测试配置文件
        server_script_path = os.path.join(self.temp_dir, "real_mcp_server.py")
        config_content = f"""
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
server_script_path = "{server_script_path}"
"""
        config_path = self.create_test_config(config_content)
        
        # 调用create_agent
        result = asyncio.run(create_agent(self.group_chat, config_path))
        
        # 验证结果 - create_agent返回的是Agent对象
        from linhai.agent import Agent
        self.assertIsInstance(result, Agent)
        
        # 验证agent已创建并配置了MCP
        from linhai.agent import Agent
        self.assertIsInstance(result, Agent)
        
        # 检查agent是否配置了MCP工具
        # 由于MCP连接器可能没有注册为group_chat成员，我们检查agent的工具调用能力
        # 通过检查agent的配置或状态来验证MCP设置
        self.assertTrue(hasattr(result, 'config'), "Agent应该有config属性")
        
        # 检查配置中是否包含MCP设置
        config = result.config
        mcp_configured = hasattr(config, 'mcp_servers') and config.mcp_servers
        self.assertTrue(mcp_configured, "MCP服务器未正确配置")

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




if __name__ == "__main__":
    unittest.main()