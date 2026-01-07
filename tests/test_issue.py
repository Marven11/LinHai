"""Issue系统单元测试。"""

import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil

from linhai.subagent.issue import IssueManager, create_issue_toolset
from linhai.group_chat import GroupChat
from linhai.config import load_config


class TestIssueManager(unittest.IsolatedAsyncioTestCase):
    """测试IssueManager功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock

        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)

        # 创建模拟的subagent_manager和subagent
        from linhai.subagent.main import SubAgentManager

        subagent = Mock()
        subagent.agent_type = "test_type"
        subagent_manager = Mock(spec=SubAgentManager)
        subagent_manager.subagents = {"test-agent": (subagent, None)}
        self.group_chat.register_member("subagent_manager", subagent_manager)

        self.manager = IssueManager(self.group_chat)
        # 注册测试subagent
        self.manager.register_subagent("test-agent", issue_limit=2)

    async def test_add_issue(self):
        """测试添加issue。"""
        issue_id = "test-123"
        content = "这是一个测试问题"
        from_subagent = "test-agent"

        await self.manager.add_issue(issue_id, content, from_subagent)

        self.assertIn(issue_id, self.manager.issues)
        issue = self.manager.issues[issue_id]
        self.assertEqual(issue["content"], content)
        self.assertEqual(issue["from_subagent"], from_subagent)
        self.assertFalse(issue["answered"])
        self.assertIsNone(issue["answer"])

    async def test_has_unanswered_issues(self):
        """测试检查未解答issue。"""
        self.assertFalse(self.manager.has_unanswered_issues())

        await self.manager.add_issue("test-1", "问题1", "test-agent")
        self.assertTrue(self.manager.has_unanswered_issues())

        import datetime

        self.manager.issues["test-1"]["created_at"] -= datetime.timedelta(minutes=3)

        self.manager.respond_issue("test-1", "回答1")
        self.assertFalse(self.manager.has_unanswered_issues())

    async def test_respond_issue(self):
        """测试回复issue。"""
        issue_id = "test-123"
        content = "测试问题"
        answer = "测试回答"

        await self.manager.add_issue(issue_id, content, "test-agent")
        import datetime

        self.manager.issues[issue_id]["created_at"] -= datetime.timedelta(minutes=3)

        self.manager.respond_issue(issue_id, answer)

        issue = self.manager.issues[issue_id]
        self.assertTrue(issue["answered"])
        self.assertEqual(issue["answer"], answer)

    async def test_get_unanswered_issues(self):
        """测试获取未解答issue列表。"""
        await self.manager.add_issue("test-1", "问题1", "test-agent")
        await self.manager.add_issue("test-2", "问题2", "test-agent")

        import datetime

        self.manager.issues["test-1"]["created_at"] -= datetime.timedelta(minutes=3)
        self.manager.issues["test-2"]["created_at"] -= datetime.timedelta(minutes=3)

        unanswered = self.manager.get_unanswered_issues()
        self.assertEqual(len(unanswered), 2)

        self.manager.respond_issue("test-1", "回答1")

        unanswered = self.manager.get_unanswered_issues()
        self.assertEqual(len(unanswered), 1)
        self.assertEqual(unanswered[0]["id"], "test-2")

    def test_respond_nonexistent_issue(self):
        """测试回复不存在的issue应返回错误消息。"""
        result = self.manager.respond_issue("nonexistent", "回答")
        self.assertIn("错误", result)
        self.assertIn("不存在", result)


class TestIssueAsync(unittest.TestCase):
    """测试Issue的异步功能。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock

        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)

        # 创建模拟的subagent_manager和subagent
        from linhai.subagent.main import SubAgentManager

        subagent = Mock()
        subagent.agent_type = "test_type"
        subagent_manager = Mock(spec=SubAgentManager)
        subagent_manager.subagents = {"test-agent": (subagent, None)}
        self.group_chat.register_member("subagent_manager", subagent_manager)

        self.manager = IssueManager(self.group_chat)
        self.manager.register_subagent("test-agent", issue_limit=2)

    def test_wait_for_nonexistent_issue(self):
        """测试等待不存在的issue应抛出异常。"""

        async def run_test():
            with self.assertRaises(ValueError) as context:
                await self.manager.wait_for_response("nonexistent")
            self.assertIn("不存在", str(context.exception))

        asyncio.run(run_test())


class TestIssueTools(unittest.IsolatedAsyncioTestCase):
    """测试issue相关工具。"""

    def setUp(self):
        """设置测试环境。"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / "config.toml"

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

        from linhai.agent import Agent
        from linhai.agent.message import AgentMessage
        from unittest.mock import Mock

        self.agent = Mock(spec=Agent)
        self.agent.state = "working"  # 添加state属性
        self.group_chat.register_member("agent", self.agent)
        self.agent_message = AgentMessage(self.group_chat)

        # 创建模拟的subagent_manager和subagent
        from linhai.subagent.main import SubAgentManager

        subagent = Mock()
        subagent.agent_type = "test_type"
        subagent_manager = Mock(spec=SubAgentManager)
        subagent_manager.subagents = {"test-agent": (subagent, None)}
        self.group_chat.register_member("subagent_manager", subagent_manager)

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.test_dir)

    async def test_agent_issue_toolset(self):
        """测试Agent的issue工具集。"""
        manager = IssueManager(self.group_chat)
        manager.register_subagent("test-agent", issue_limit=2)
        toolset = create_issue_toolset(manager)

        issue_id = "tool-test-123"
        await manager.add_issue(issue_id, "工具测试问题", "test-agent")

        import datetime

        manager.issues[issue_id]["created_at"] -= datetime.timedelta(minutes=3)

        result = toolset.call_tool(
            "respond_issue", {"issue_id": issue_id, "answer": "工具测试回答"}
        )

        self.assertIn("成功回复issue", result)
        self.assertTrue(manager.issues[issue_id]["answered"])

    def test_agent_issue_toolset_error(self):
        """测试Agent回复不存在的issue。"""
        manager = IssueManager(self.group_chat)
        manager.register_subagent("test-agent", issue_limit=2)
        toolset = create_issue_toolset(manager)

        result = toolset.call_tool(
            "respond_issue", {"issue_id": "nonexistent", "answer": "回答"}
        )

        self.assertIn("错误", result)
        self.assertIn("不存在", result)


if __name__ == "__main__":
    unittest.main()
