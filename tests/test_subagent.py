"""SubAgent系统测试。"""

import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil

from linhai.subagent import SubAgentManager
from linhai.group_chat import GroupChat
from linhai.agent import create_agent
from linhai.config import load_config


class TestSubAgent(unittest.TestCase):
    """测试SubAgent功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / "config.toml"
        
        # 创建测试配置
        config_content = '''
[[llm]]
name = "test"
api_key = "test-key"
base_url = "https://api.openai.com/v1"
model = "gpt-3.5-turbo"

[tools]
max_output_length = 50000

[memory]
file_path = "memory.md"

[subagent]
enable = true
default_llm = "test"
'''
        self.config_path.write_text(config_content)
        
        # 加载配置
        self.config = load_config(self.config_path)
        self.group_chat = GroupChat()

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.test_dir)

    async def _create_agent(self):
        """异步创建Agent。"""
        return await create_agent(self.group_chat, self.config_path)

    def test_subagent_manager_creation(self):
        """测试SubAgentManager创建。"""
        manager = SubAgentManager(self.group_chat)
        self.assertIsNotNone(manager)
        self.assertEqual(len(manager.subagents), 0)

    def test_create_subagent(self):
        """测试创建SubAgent。"""
        async def run_test():
            # 创建Agent（会自动创建SubAgentManager并注册工具）
            agent = await self._create_agent()
            
            # 获取SubAgentManager（注意get_members返回单个对象）
            from linhai.subagent import SubAgentManager
            manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
            # 确保manager是单个对象而不是元组
            if isinstance(manager, tuple):
                manager = manager[0]
            
            # 创建SubAgent
            result = await manager.create_subagent("clarifier", "test-agent", "睡眠5秒然后退出", max_answer_times=None)
            self.assertIn("成功创建SubAgent test-agent", result)
            self.assertIn("test-agent", manager.subagents)
            
            # 检查初始状态
            status = await manager.check_subagent("test-agent")
            self.assertIn("正在运行", status)
        
        asyncio.run(run_test())

    def test_check_nonexistent_subagent(self):
        """测试检查不存在的SubAgent。"""
        async def run_test():
            manager = SubAgentManager(self.group_chat)
            result = await manager.check_subagent("nonexistent")
            self.assertIn("不存在", result)
        asyncio.run(run_test())

    def test_create_duplicate_subagent(self):
        """测试创建重复的SubAgent。"""
        async def run_test():
            # 创建Agent（会自动创建SubAgentManager并注册工具）
            agent = await self._create_agent()
            
            # 获取SubAgentManager（注意get_members返回单个对象）
            from linhai.subagent import SubAgentManager
            manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
            # 确保manager是单个对象而不是元组
            if isinstance(manager, tuple):
                manager = manager[0]
            
            # 创建第一个
            await manager.create_subagent("clarifier", "duplicate", "任务", max_answer_times=None)
            
            # 尝试创建第二个同名
            result = await manager.create_subagent("dummy", "duplicate", "任务", max_answer_times=None)
            self.assertIn("已存在", result)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
