"""SubAgent系统测试。"""

import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil

from linhai.subagent import SubAgentManager
from linhai.group_chat import GroupChat
from linhai.agent.create import create_agent_from_config
from linhai.config import load_config


class TestSubAgent(unittest.TestCase):
    """测试SubAgent功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / "config.toml"
        
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
        
        self.config = load_config(self.config_path)
        self.group_chat = GroupChat()

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.test_dir)

    async def _create_agent(self):
        """异步创建Agent。"""
        return await create_agent_from_config(self.group_chat, self.config)

    def test_subagent_manager_creation(self):
        """测试SubAgentManager创建。"""
        manager = SubAgentManager(self.group_chat, self.config.subagent)
        self.assertIsNotNone(manager)
        self.assertEqual(len(manager.subagents), 0)

    def test_create_subagent(self):
        """测试创建SubAgent。"""
        async def run_test():
            agent = await self._create_agent()
            
            from linhai.subagent import SubAgentManager
            manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
            if isinstance(manager, tuple):
                manager = manager[0]
            
            result = await manager.create_subagent("violation_checker", "test-agent", "睡眠5秒然后退出", max_answer_times=None)
            self.assertIn("成功创建SubAgent test-agent", result)
            self.assertIn("test-agent", manager.subagents)
            
            status = await manager.check_subagent("test-agent")
            self.assertIn("正在运行", status)
        
        asyncio.run(run_test())

    def test_check_nonexistent_subagent(self):
        """测试检查不存在的SubAgent。"""
        async def run_test():
            manager = SubAgentManager(self.group_chat, self.config.subagent)
            result = await manager.check_subagent("nonexistent")
            self.assertIn("不存在", result)
        asyncio.run(run_test())

    def test_create_duplicate_subagent(self):
        """测试创建重复的SubAgent。"""
        async def run_test():
            agent = await self._create_agent()
            
            from linhai.subagent import SubAgentManager
            manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
            if isinstance(manager, tuple):
                manager = manager[0]
            
            await manager.create_subagent("violation_checker", "duplicate", "任务", max_answer_times=None)
            
            result = await manager.create_subagent("git_diff_reviewer", "duplicate", "任务", max_answer_times=None)
            self.assertIn("已存在", result)
        
        asyncio.run(run_test())

    def test_tool_failure_sends_ui_message(self):
        """测试工具失败时发送UI消息到SubAgent Tab。"""
        async def run_test():
            agent = await self._create_agent()
            
            from linhai.subagent import SubAgentManager
            manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
            if isinstance(manager, tuple):
                manager = manager[0]
            
            self.group_chat.register_queue("subagent_message")
            
            from linhai.subagent.main import SubAgent
            from linhai.llm import UserMessage, AssistantMessage
            
            class TestSubAgent(SubAgent):
                def get_system_message_prompt(self):
                    return "测试SubAgent，请调用工具。"
            
            llm_name, llm = agent.get_current_llm_info()
            
            test_subagent = TestSubAgent(
                agent_type="test",
                name="test-failure",
                task_message="调用一个不存在的工具：\n\n```json toolcall\n{\"name\": \"nonexistent_tool\", \"arguments\": {\"test\": \"value\"}}\n```\n\n然后退出。",
                llm=llm,
                group_chat=self.group_chat,
                max_answer_times=1
            )
            
            if "subagent_message" not in self.group_chat.queues:
                self.group_chat.register_queue("subagent_message")
            
            tool_calls = [{"name": "sleep", "arguments": {"seconds": "invalid_number"}}]
            await test_subagent._execute_tool_calls(tool_calls)
            
            try:
                message = await asyncio.wait_for(self.group_chat.receive("subagent_message"), timeout=1.0)
                
                from linhai.utils import CliRuntimeNotice
                self.assertIsInstance(message, CliRuntimeNotice)
                self.assertEqual(message.level, "ERROR")
                self.assertIn("执行失败", message.content)
                self.assertIn("sleep", message.content)
                
            except asyncio.TimeoutError:
                self.fail("未在超时时间内收到预期的UI消息")
        
        asyncio.run(run_test())


    def test_subagent_clarification_limit(self):
        """测试SubAgent澄清请求限制机制。"""
        async def run_test():
            agent = await self._create_agent()
            
            from linhai.subagent.clarification import ClarificationManager
            clarification_manager = self.group_chat.get_members("clarification_manager", ClarificationManager)
            if isinstance(clarification_manager, tuple):
                clarification_manager = clarification_manager[0]
            
            result1 = await clarification_manager.request_clarification("clarification_1", "第一个问题", "test-agent")
            self.assertIsNone(result1)  # 返回None表示成功
            self.assertEqual(clarification_manager.subagent_request_count["test-agent"], 1)
            
            result2 = await clarification_manager.request_clarification("clarification_2", "第二个问题", "test-agent")
            self.assertIsNotNone(result2)  # 返回错误字符串表示被阻止，因为限制已改为1次
            self.assertIn("超过1次", str(result2))
            self.assertEqual(clarification_manager.subagent_request_count["test-agent"], 1)  # 计数不应增加
            
            result3 = await clarification_manager.request_clarification("clarification_3", "第三个问题", "test-agent")
            self.assertIsNotNone(result3)  # 返回错误字符串表示被阻止
            self.assertIn("超过1次", str(result3))
            self.assertEqual(clarification_manager.subagent_request_count["test-agent"], 1)  # 计数不应增加
            
            result4 = await clarification_manager.request_clarification("clarification_4", "另一个agent的问题", "other-agent")
            self.assertIsNone(result4)  # 返回None表示成功
            self.assertEqual(clarification_manager.subagent_request_count["other-agent"], 1)
        
        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()