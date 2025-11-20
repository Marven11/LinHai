"""测试create_agent函数的基本功能"""

import unittest
from unittest.mock import patch, AsyncMock
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.group_chat import GroupChat
from linhai.agent import create_agent, Agent
from linhai.tool.main import ToolManager


class TestCreateAgent(unittest.TestCase):
    """测试create_agent函数"""

    @patch('linhai.tool.mcp_connector.MCPConnector')
    def test_create_agent_basic_functionality(self, mock_mcp_connector):
        """测试create_agent基本功能：创建agent并返回group_chat"""
        # 模拟MCP连接器
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance
        
        group_chat = GroupChat()
        config_path = Path(__file__).parent / "config.toml"
        
        # 调用create_agent应该成功返回agent
        result = asyncio.run(create_agent(group_chat, Path(config_path)))
        self.assertIsInstance(result, Agent)
        
        # 检查group_chat中是否注册了agent成员
        try:
            agent = group_chat.get_members("agent", Agent)
            self.assertIsNotNone(agent)
        except RuntimeError:
            self.fail("agent成员未在group_chat中注册")
        
        # 检查group_chat中是否注册了tool_manager成员
        try:
            tool_manager = group_chat.get_members("tool_manager", ToolManager)
            self.assertIsNotNone(tool_manager)
        except RuntimeError:
            self.fail("tool_manager成员未在group_chat中注册")

    @patch('linhai.tool.mcp_connector.MCPConnector')
    def test_create_agent_with_llm_name(self, mock_mcp_connector):
        """测试使用llm_name参数创建agent"""
        # 模拟MCP连接器
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.get_toolsets.return_value = []
        mock_mcp_connector.return_value = mock_mcp_instance
        
        group_chat = GroupChat()
        config_path = Path(__file__).parent / "config.toml"
        
        # 使用llm_name参数
        result = asyncio.run(create_agent(group_chat, Path(config_path), llm_name="test"))
        self.assertIsInstance(result, Agent)
        
        # 检查agent配置中的当前LLM索引
        agent = group_chat.get_members("agent", Agent)
        self.assertEqual(agent.context["current_llm_index"], 0)  # test是第一个LLM

    def test_create_agent_with_invalid_llm_name(self):
        """测试使用无效的llm_name参数应抛出错误"""
        group_chat = GroupChat()
        config_path = Path(__file__).parent / "config.toml"
        
        # 使用无效的llm_name应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            asyncio.run(create_agent(group_chat, Path(config_path), llm_name="invalid_llm"))
        
        self.assertIn("LLM名称 'invalid_llm' 不存在", str(context.exception))


if __name__ == "__main__":
    unittest.main()