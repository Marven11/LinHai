"""测试SubAgent配置功能。"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock

from linhai.subagent.main import SubAgentManager
from linhai.config import SubAgentConfig


class TestSubAgentConfig(unittest.IsolatedAsyncioTestCase):
    """测试SubAgent配置功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = Mock()
        self.group_chat.register_member = Mock()
        
        # 创建模拟的LLM
        self.mock_llm1 = Mock()
        self.mock_llm1.name = "deepseek"
        self.mock_llm2 = Mock()
        self.mock_llm2.name = "qwen"
        
        self.llms = [self.mock_llm1, self.mock_llm2]
        self.llm_names = ["deepseek", "qwen"]

    async def test_create_subagent_with_config_default_llm(self):
        """测试使用配置中的default_llm创建SubAgent。"""
        # 创建配置
        subagent_config = SubAgentConfig(default_llm="qwen")
        
        # 创建SubAgentManager
        manager = SubAgentManager(
            self.group_chat, 
            subagent_config, 
            self.llms, 
            self.llm_names
        )
        
        # 创建SubAgent
        result = await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="测试任务",
            llm=self.mock_llm1  # 传入的llm将被配置覆盖
        )
        
        # 验证结果
        self.assertIn("成功创建SubAgent test_agent", result)
        
        # 验证SubAgent使用了配置的LLM
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm2)  # 应该使用qwen而不是deepseek

    async def test_create_subagent_without_config(self):
        """测试没有配置时使用传入的LLM创建SubAgent。"""
        # 创建SubAgentManager（没有配置）
        manager = SubAgentManager(
            self.group_chat, 
            None, 
            self.llms, 
            self.llm_names
        )
        
        # 创建SubAgent
        result = await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="测试任务",
            llm=self.mock_llm1
        )
        
        # 验证结果
        self.assertIn("成功创建SubAgent test_agent", result)
        
        # 验证SubAgent使用了传入的LLM
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_subagent_with_invalid_default_llm(self):
        """测试配置的default_llm不存在时使用传入的LLM。"""
        # 创建配置（使用不存在的LLM）
        subagent_config = SubAgentConfig(default_llm="nonexistent")
        
        # 创建SubAgentManager
        manager = SubAgentManager(
            self.group_chat, 
            subagent_config, 
            self.llms, 
            self.llm_names
        )
        
        # 创建SubAgent
        result = await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="测试任务",
            llm=self.mock_llm1
        )
        
        # 验证结果
        self.assertIn("成功创建SubAgent test_agent", result)
        
        # 验证SubAgent使用了传入的LLM（因为配置的LLM不存在）
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_duplicate_subagent(self):
        """测试创建重复的SubAgent。"""
        manager = SubAgentManager(self.group_chat)
        
        # 第一次创建
        result1 = await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="测试任务",
            llm=self.mock_llm1
        )
        self.assertIn("成功创建SubAgent test_agent", result1)
        
        # 第二次创建相同名称的SubAgent
        result2 = await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="另一个任务",
            llm=self.mock_llm2
        )
        self.assertIn("错误: SubAgent test_agent 已存在", result2)

    async def test_check_subagent_status(self):
        """测试检查SubAgent状态。"""
        manager = SubAgentManager(self.group_chat)
        
        # 创建SubAgent
        await manager.create_subagent(
            agent_type="test",
            name="test_agent",
            task_message="测试任务",
            llm=self.mock_llm1
        )
        
        # 检查状态
        status = await manager.check_subagent("test_agent")
        self.assertIn("SubAgent test_agent 正在运行", status)
        
        # 检查不存在的SubAgent
        status = await manager.check_subagent("nonexistent")
        self.assertIn("错误: SubAgent nonexistent 不存在", status)


if __name__ == "__main__":
    unittest.main()