"""澄清系统单元测试。"""

import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil

from linhai.subagent.clarification import ClarificationManager
from linhai.group_chat import GroupChat
from linhai.agent.clarification_tools import create_clarification_toolset as create_agent_clarification_toolset
from linhai.config import load_config


class TestClarificationManager(unittest.IsolatedAsyncioTestCase):
    """测试ClarificationManager功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        # 注册模拟的agent和agent_message以避免运行时错误
        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock
        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)
        self.manager = ClarificationManager(self.group_chat)

    async def test_add_clarification(self):
        """测试添加澄清问题。"""
        clarification_id = "test-123"
        question = "这是一个测试问题"
        from_subagent = "test-agent"

        await self.manager.add_clarification(clarification_id, question, from_subagent)

        self.assertIn(clarification_id, self.manager.clarifications)
        clarification = self.manager.clarifications[clarification_id]
        self.assertEqual(clarification["question"], question)
        self.assertEqual(clarification["from_subagent"], from_subagent)
        self.assertFalse(clarification["answered"])
        self.assertIsNone(clarification["answer"])

    async def test_has_unanswered_clarifications(self):
        """测试检查未解答澄清。"""
        # 初始时没有澄清
        self.assertFalse(self.manager.has_unanswered_clarifications())

        # 添加未解答的澄清
        await self.manager.add_clarification("test-1", "问题1", "agent-1")
        self.assertTrue(self.manager.has_unanswered_clarifications())

        import datetime
        self.manager.clarifications["test-1"]["created_at"] -= datetime.timedelta(minutes=3)

        # 回复澄清
        self.manager.respond_clarification("test-1", "回答1")
        self.assertFalse(self.manager.has_unanswered_clarifications())

    async def test_respond_clarification(self):
        """测试回复澄清。"""
        clarification_id = "test-123"
        question = "测试问题"
        answer = "测试回答"

        await self.manager.add_clarification(clarification_id, question, "test-agent")
        # 修改创建时间为两分钟前，以绕过时间限制
        import datetime
        self.manager.clarifications[clarification_id]["created_at"] -= datetime.timedelta(minutes=3)

        self.manager.respond_clarification(clarification_id, answer)

        clarification = self.manager.clarifications[clarification_id]
        self.assertTrue(clarification["answered"])
        self.assertEqual(clarification["answer"], answer)

    async def test_get_unanswered_clarifications(self):
        """测试获取未解答澄清列表。"""
        # 添加两个未解答的澄清
        await self.manager.add_clarification("test-1", "问题1", "agent-1")
        await self.manager.add_clarification("test-2", "问题2", "agent-2")

        # 修改创建时间为两分钟前，以绕过时间限制
        import datetime
        self.manager.clarifications["test-1"]["created_at"] -= datetime.timedelta(minutes=3)
        self.manager.clarifications["test-2"]["created_at"] -= datetime.timedelta(minutes=3)

        unanswered = self.manager.get_unanswered_clarifications()
        self.assertEqual(len(unanswered), 2)

        # 回复其中一个
        self.manager.respond_clarification("test-1", "回答1")

        unanswered = self.manager.get_unanswered_clarifications()
        self.assertEqual(len(unanswered), 1)
        self.assertEqual(unanswered[0]["id"], "test-2")

    def test_respond_nonexistent_clarification(self):
        """测试回复不存在的澄清应抛出异常。"""
        with self.assertRaises(ValueError) as context:
            self.manager.respond_clarification("nonexistent", "回答")
        self.assertIn("不存在", str(context.exception))


class TestClarificationAsync(unittest.TestCase):
    """测试Clarification的异步功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        # 注册模拟的agent和agent_message以避免运行时错误
        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock
        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)
        self.manager = ClarificationManager(self.group_chat)

    def test_wait_for_nonexistent_clarification(self):
        """测试等待不存在的澄清应抛出异常。"""

        async def run_test():
            with self.assertRaises(ValueError) as context:
                await self.manager.wait_for_response("nonexistent")
            self.assertIn("不存在", str(context.exception))

        asyncio.run(run_test())


class TestClarificationTools(unittest.IsolatedAsyncioTestCase):
    """测试澄清相关工具。"""

    def setUp(self):
        """设置测试环境。"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / "config.toml"

        # 创建测试配置
        config_content = """
[[llm]]
name = "test"
api_key = "test-key"
base_url = "https://api.openai.com/v1"
model = "gpt-3.5-turbo"

[tools]
max_output_length = 50000

[memory]
file_path = "memory.md"
"""
        self.config_path.write_text(config_content)
        self.config = load_config(self.config_path)
        self.group_chat = GroupChat()
        
        # 注册模拟的agent和agent_message以避免运行时错误
        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock
        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.test_dir)

    async def test_agent_clarification_toolset(self):
        """测试Agent的澄清工具集。"""
        manager = ClarificationManager(self.group_chat)
        toolset = create_agent_clarification_toolset(manager)

        # 添加一个澄清
        clarification_id = "tool-test-123"
        await manager.add_clarification(clarification_id, "工具测试问题", "test-agent")

        # 修改clarification的创建时间为两分钟前，以绕过时间限制
        import datetime
        manager.clarifications[clarification_id]["created_at"] -= datetime.timedelta(minutes=3)

        # 使用工具回复
        result = toolset.call_tool("respond_clarification", {
            "clarification_id": clarification_id,
            "answer": "工具测试回答"
        })

        self.assertIn("成功回复澄清", result)
        self.assertTrue(manager.clarifications[clarification_id]["answered"])

    def test_agent_clarification_toolset_error(self):
        """测试Agent回复不存在的澄清。"""
        manager = ClarificationManager(self.group_chat)
        toolset = create_agent_clarification_toolset(manager)

        result = toolset.call_tool("respond_clarification", {
            "clarification_id": "nonexistent",
            "answer": "回答"
        })

        self.assertIn("错误", result)
        self.assertIn("不存在", result)


if __name__ == "__main__":
    unittest.main()
