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

[subagent]
enable = true
default_llm = "test"
"""
        self.config_path.write_text(config_content)

        self.config = load_config(self.config_path)
        self.group_chat = GroupChat()

        # 注册模拟的cli_args，因为subagent_manager.register_plugins()需要它
        import argparse

        self.cli_args = argparse.Namespace()
        self.cli_args.checklist = None
        self.cli_args.git_diff_reviewer = False
        self.cli_args.violation_checker = False
        self.cli_args.message = None
        self.cli_args.file = None
        self.group_chat.register_member("cli_args", self.cli_args)

    def tearDown(self):
        """清理测试环境。"""
        shutil.rmtree(self.test_dir)

    async def _create_agent(self):
        """异步创建Agent。"""
        from pathlib import Path

        context = {
            "group_chat": self.group_chat,
            "config": self.config,
            "config_basedir": Path("."),
            "llm_name": None,
            "max_toolcall_token_in_round": 30000,
            "checklist_path": None,
            "git_diff_reviewer": self.cli_args.git_diff_reviewer,
            "violation_checker": self.cli_args.violation_checker,
            "cli_args": self.cli_args,
        }
        return await create_agent_from_config(context)

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

            result = await manager.create_subagent(
                "violation_checker",
                "test-agent",
                "睡眠5秒然后退出",
                max_answer_times=None,
            )
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

            await manager.create_subagent(
                "violation_checker", "duplicate", "任务", max_answer_times=None
            )

            result = await manager.create_subagent(
                "git_diff_reviewer", "duplicate", "任务", max_answer_times=None
            )
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
                task_message='调用一个不存在的工具：\n\n```json toolcall\n{"name": "nonexistent_tool", "arguments": {"test": "value"}}\n```\n\n然后退出。',
                llm=llm,
                group_chat=self.group_chat,
                max_answer_times=1,
            )

            if "subagent_message" not in self.group_chat.queues:
                self.group_chat.register_queue("subagent_message")

            tool_calls = [{"name": "sleep", "arguments": {"seconds": "invalid_number"}}]
            await test_subagent._execute_tool_calls(tool_calls)

            try:
                message = await asyncio.wait_for(
                    self.group_chat.receive("subagent_message"), timeout=1.0
                )

                from linhai.utils import CliRuntimeNotice

                self.assertIsInstance(message, CliRuntimeNotice)
                self.assertEqual(message.level, "ERROR")
                self.assertIn("执行失败", message.content)
                self.assertIn("sleep", message.content)

            except asyncio.TimeoutError:
                self.fail("未在超时时间内收到预期的UI消息")

        asyncio.run(run_test())

    def test_subagent_exits_immediately_on_last_issue(self):
        """测试SubAgent在最后一个issue后立即退出。"""

        async def run_test():
            import sys

            agent = await self._create_agent()

            from linhai.subagent import SubAgentManager
            from linhai.subagent.issue import IssueManager
            from linhai.subagent.main import SubAgent
            from linhai.subagent.issue_tools import create_issue_toolset

            # 获取管理器
            subagent_manager = self.group_chat.get_members(
                "subagent_manager", SubAgentManager
            )
            if isinstance(subagent_manager, tuple):
                subagent_manager = subagent_manager[0]

            issue_manager = self.group_chat.get_members("issue_manager", IssueManager)
            if isinstance(issue_manager, tuple):
                issue_manager = issue_manager[0]

            # 创建测试subagent类
            class TestSubAgent(SubAgent):
                def get_system_message_prompt(self):
                    return "测试SubAgent，请调用工具。"

            # 获取LLM
            llm_name, llm = agent.get_current_llm_info()

            # 创建subagent，设置issue限额为1
            test_subagent = TestSubAgent(
                agent_type="test",
                name="test-exit",
                task_message="测试在最后一个issue后立即退出",
                llm=llm,
                group_chat=self.group_chat,
                max_answer_times=5,
            )

            # 注册到管理器
            subagent_manager.subagents["test-exit"] = (test_subagent, None)

            # 注册到issue_manager，设置限额为1
            issue_manager.register_subagent("test-exit", issue_limit=1)

            # 创建issue工具集
            toolset = create_issue_toolset(issue_manager, test_subagent)

            # 调用request_issue（第一个也是最后一个issue）
            result = await toolset.call_tool(
                "request_issue", {"content": "测试issue内容"}
            )

            # 验证subagent立即退出
            self.assertEqual(test_subagent.state, "exited")
            self.assertIsNotNone(test_subagent.exit_reason)
            self.assertIn("限额", str(test_subagent.exit_reason))

            # 验证issue计数为1
            self.assertEqual(issue_manager.subagent_issue_count["test-exit"], 1)

            # 验证没有生成新的消息（subagent已退出）
            # subagent在exited状态不会执行任何操作

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
