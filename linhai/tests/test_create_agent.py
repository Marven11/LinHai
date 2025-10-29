"""测试create_agent函数的基本功能"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linhai.group_chat import GroupChat
from linhai.agent import create_agent


class TestCreateAgent(unittest.TestCase):
    """测试create_agent函数"""

    async def test_create_agent_basic_functionality(self):
        """测试create_agent基本功能：创建agent并返回group_chat"""
        group_chat = GroupChat()
        config_path = "./config.toml"
        
        # 调用create_agent应该成功返回group_chat
        result = await create_agent(group_chat, config_path)
        self.assertIsInstance(result, GroupChat)
        self.assertEqual(result, group_chat)
        
        # 检查group_chat中是否注册了agent成员
        try:
            from linhai.agent import Agent
            agent = group_chat.get_members("agent", Agent)
            self.assertIsNotNone(agent)
        except RuntimeError:
            self.fail("agent成员未在group_chat中注册")
        
        # 检查group_chat中是否注册了tool_manager成员
        try:
            from linhai.tool.main import ToolManager
            tool_manager = group_chat.get_members("tool_manager", ToolManager)
            self.assertIsNotNone(tool_manager)
        except RuntimeError:
            self.fail("tool_manager成员未在group_chat中注册")

    async def test_create_agent_with_llm_name(self):
        """测试使用llm_name参数创建agent"""
        group_chat = GroupChat()
        config_path = "./config.toml"
        
        # 使用llm_name参数
        result = await create_agent(group_chat, config_path, llm_name="deepseek")
        self.assertIsInstance(result, GroupChat)
        
        # 检查agent配置中的当前LLM索引
        from linhai.agent import Agent
        agent = group_chat.get_members("agent", Agent)
        self.assertEqual(agent.config["current_llm_index"], 0)  # 假设deepseek是第一个LLM

    async def test_create_agent_with_invalid_llm_name(self):
        """测试使用无效的llm_name参数应抛出错误"""
        group_chat = GroupChat()
        config_path = "./config.toml"
        
        # 使用无效的llm_name应该抛出ValueError
        with self.assertRaises(ValueError) as context:
            await create_agent(group_chat, config_path, llm_name="invalid_llm")
        
        self.assertIn("LLM名称 'invalid_llm' 不存在", str(context.exception))


if __name__ == "__main__":
    unittest.main()