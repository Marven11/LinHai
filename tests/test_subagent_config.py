"""测试SubAgent配置功能。"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

from linhai.subagent.main import SubAgentManager
from linhai.config import SubAgentConfig


class TestSubAgentConfig(unittest.IsolatedAsyncioTestCase):
    """测试SubAgent配置功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = AsyncMock()
        self.group_chat.register_member = Mock()
        self.group_chat.send_if_exists = AsyncMock()
        self.group_chat.receive = AsyncMock()
        self.group_chat.is_empty = Mock(return_value=True)
        self.group_chat._test_mode = True  # 标记为测试模式，防止SubAgent实际运行
        
        # 创建模拟的LLM - 使用AsyncMock以便可以await
        self.mock_llm1 = AsyncMock()
        self.mock_llm1.name = "deepseek"
        self.mock_llm1.answer_stream = AsyncMock()
        self.mock_llm2 = AsyncMock()
        self.mock_llm2.name = "qwen"
        self.mock_llm2.answer_stream = AsyncMock()
        
        self.llms = [self.mock_llm1, self.mock_llm2]
        self.llm_names = ["deepseek", "qwen"]
        
        # 设置group_chat.get_members返回正确的格式（单个对象）
        self.mock_agent = MagicMock()
        self.mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm1))
        self.group_chat.get_members = Mock(return_value=self.mock_agent)

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
        # 设置manager的group_chat.get_members返回正确的agent（单个对象）
        mock_agent = MagicMock()
        mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm2))
        manager.group_chat.get_members = Mock(return_value=mock_agent)
        
        # 创建SubAgent
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
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
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        # 验证结果
        self.assertIn("成功创建SubAgent test_agent", result)
        
        # 验证SubAgent使用了传入的LLM
        subagent, _ = manager.subagents["test_agent"]
        # 由于使用了agent.get_current_llm_info，这里应该验证返回的LLM
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_subagent_with_invalid_default_llm(self):
        """测试配置的default_llm不存在时使用第一个可用LLM。"""
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
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        # 验证结果
        self.assertIn("成功创建SubAgent test_agent", result)
        
        # 验证SubAgent使用了第一个可用LLM（因为配置的LLM不存在）
        subagent, _ = manager.subagents["test_agent"]
        # 在测试模式下，当配置的default_llm不存在时，会使用第一个可用LLM
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_duplicate_subagent(self):
        """测试创建重复的SubAgent。"""
        # 创建配置，确保使用直接传递的LLM
        subagent_config = SubAgentConfig(default_llm="deepseek")
        manager = SubAgentManager(self.group_chat, subagent_config, self.llms, self.llm_names)
        
        # 手动添加一个模拟的SubAgent到manager.subagents中，测试重复创建逻辑
        mock_subagent = type('MockSubAgent', (), {
            'agent_type': 'test',
            'name': 'test_agent',
            'task_message': '测试任务',
            'llm': None,
            'group_chat': self.group_chat,
            'state': 'running',
            'exit_reason': None,
            'start_time': datetime.now(),
            'max_answer_times': None
        })()
        manager.subagents['test_agent'] = (mock_subagent, None)  # type: ignore
        
        # 尝试创建相同名称的SubAgent
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="另一个任务",
            max_answer_times=None
        )
        self.assertIn("错误: SubAgent test_agent 已存在", result)

    async def test_check_subagent_status(self):
        """测试检查SubAgent状态。"""
        manager = SubAgentManager(self.group_chat)
        # 设置manager的group_chat.get_members返回正确的agent（单个对象）
        mock_agent = MagicMock()
        mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm1))
        manager.group_chat.get_members = Mock(return_value=mock_agent)
        
        # 创建SubAgent
        await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        # 检查状态
        status = await manager.check_subagent("test_agent")
        self.assertIn("SubAgent test_agent 正在运行", status)
        
        # 检查不存在的SubAgent
        status = await manager.check_subagent("nonexistent")
        self.assertIn("错误: SubAgent nonexistent 不存在", status)


if __name__ == "__main__":
    unittest.main()