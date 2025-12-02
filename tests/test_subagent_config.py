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
        
        self.mock_llm1 = AsyncMock()
        self.mock_llm1.name = "deepseek"
        self.mock_llm1.answer_stream = AsyncMock()
        self.mock_llm2 = AsyncMock()
        self.mock_llm2.name = "qwen"
        self.mock_llm2.answer_stream = AsyncMock()
        
        self.llms = [self.mock_llm1, self.mock_llm2]
        self.llm_names = ["deepseek", "qwen"]
        
        self.mock_agent = MagicMock()
        self.mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm1))
        self.group_chat.get_members = Mock(return_value=self.mock_agent)

    async def test_create_subagent_with_config_default_llm(self):
        """测试使用配置中的default_llm创建SubAgent。"""
        subagent_config = SubAgentConfig(default_llm="qwen")
        
        manager = SubAgentManager(
            self.group_chat, 
            subagent_config, 
            self.llms, 
            self.llm_names
        )
        mock_agent = MagicMock()
        mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm2))
        manager.group_chat.get_members = Mock(return_value=mock_agent)
        
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        self.assertIn("成功创建SubAgent test_agent", result)
        
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm2)  # 应该使用qwen而不是deepseek

    async def test_create_subagent_without_config(self):
        """测试没有配置时使用传入的LLM创建SubAgent。"""
        subagent_config = SubAgentConfig(default_llm="deepseek")
        manager = SubAgentManager(
            self.group_chat, 
            subagent_config, 
            self.llms, 
            self.llm_names
        )
        
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        self.assertIn("成功创建SubAgent test_agent", result)
        
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_subagent_with_invalid_default_llm(self):
        """测试配置的default_llm不存在时使用第一个可用LLM。"""
        subagent_config = SubAgentConfig(default_llm="nonexistent")
        
        manager = SubAgentManager(
            self.group_chat, 
            subagent_config, 
            self.llms, 
            self.llm_names
        )
        
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        self.assertIn("成功创建SubAgent test_agent", result)
        
        subagent, _ = manager.subagents["test_agent"]
        self.assertEqual(subagent.llm, self.mock_llm1)

    async def test_create_duplicate_subagent(self):
        """测试创建重复的SubAgent。"""
        subagent_config = SubAgentConfig(default_llm="deepseek")
        manager = SubAgentManager(self.group_chat, subagent_config, self.llms, self.llm_names)
        
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
        
        result = await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="另一个任务",
            max_answer_times=None
        )
        self.assertIn("错误: SubAgent test_agent 已存在", result)

    async def test_check_subagent_status(self):
        """测试检查SubAgent状态。"""
        subagent_config = SubAgentConfig(default_llm="deepseek")
        manager = SubAgentManager(self.group_chat, subagent_config)
        mock_agent = MagicMock()
        mock_agent.get_current_llm_info = Mock(return_value=(None, self.mock_llm1))
        manager.group_chat.get_members = Mock(return_value=mock_agent)
        
        await manager.create_subagent(
            agent_type="violation_checker",
            name="test_agent",
            task_message="测试任务",
            max_answer_times=None
        )
        
        status = await manager.check_subagent("test_agent")
        self.assertIn("SubAgent test_agent 正在运行", status)
        
        status = await manager.check_subagent("nonexistent")
        self.assertIn("错误: SubAgent nonexistent 不存在", status)


if __name__ == "__main__":
    unittest.main()