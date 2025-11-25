"""测试GitBlockingPlugin"""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.agent.plugin import GitBlockingPlugin
from linhai.agent.base import RuntimeMessage
from linhai.llm import ToolCallMessage


class TestGitBlockingPlugin(unittest.IsolatedAsyncioTestCase):
    """测试GitBlockingPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.append_message = MagicMock()
        
        self.clarification_manager = MagicMock()
        self.clarification_manager.has_unanswered_clarifications.return_value = False
        
        self.group_chat = MagicMock()
        # 设置get_members根据参数返回不同的对象
        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            elif member_type == "clarification_manager":
                return self.clarification_manager
            return None
        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)
        
        self.plugin = GitBlockingPlugin(self.group_chat)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_before_tool_call.assert_called_once_with(
            self.plugin.before_tool_call
        )

    async def test_git_command_detection(self):
        """测试git命令检测。"""
        # 测试各种git命令
        test_cases = [
            ("git status", True),
            ("git commit -m 'test'", True),
            ("git push", True),
            ("git-log", True),
            ("/usr/bin/git status", True),
            ("/usr/local/bin/git", True),
            ("mygit command", False),
            ("echo 'git is great'", False),
            ("ls -la", False),
            ("python script.py", False),
        ]
        
        for command, expected in test_cases:
            with self.subTest(command=command):
                result = self.plugin._is_git_command(command)
                self.assertEqual(result, expected, f"Failed for command: {command}")

    async def test_block_git_command_with_unanswered_clarifications(self):
        """测试有未解答澄清时阻止git命令。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="run_simple_command",
            function_arguments={"command": "git status"}
        )
        
        # 应该返回True阻止工具调用
        result = await self.plugin.before_tool_call(tool_call)
        self.assertTrue(result)
        self.agent.message_processor.append_message.assert_called_once()

    async def test_allow_git_command_without_unanswered_clarifications(self):
        """测试没有未解答澄清时允许git命令。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = False
        
        tool_call = ToolCallMessage(
            function_name="run_simple_command", 
            function_arguments={"command": "git status"}
        )
        
        # 应该返回False允许工具调用
        result = await self.plugin.before_tool_call(tool_call)
        self.assertFalse(result)
        self.agent.message_processor.append_message.assert_not_called()

    async def test_ignore_non_command_tools(self):
        """测试忽略非命令工具。"""
        self.clarification_manager.has_unanswered_clarifications.return_value = True
        
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "test.txt"}
        )
        
        # 应该返回False允许工具调用
        result = await self.plugin.before_tool_call(tool_call)
        self.assertFalse(result)
        self.agent.message_processor.append_message.assert_not_called()