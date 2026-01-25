"""测试GitBlockingPlugin"""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.subagent.plugin import GitBlockingPlugin


class TestGitBlockingPlugin(unittest.IsolatedAsyncioTestCase):
    """测试GitBlockingPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()

        self.issue_manager = MagicMock()
        self.issue_manager.has_unanswered_issues.return_value = False

        self.group_chat = MagicMock()

        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            elif member_type == "issue_manager":
                return self.issue_manager
            return None

        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)

        self.plugin = GitBlockingPlugin(self.group_chat)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_on_tool_result.assert_called_once_with(
            self.plugin.on_tool_result
        )

    async def test_block_git_command_with_unanswered_issues(self):
        """测试有未解答issue时阻止git命令。"""
        self.issue_manager.has_unanswered_issues.return_value = True

        self.group_chat.send_if_exists = AsyncMock()

        result = await self.plugin.on_tool_result(
            tool_name="process_create",
            tool_index=0,
            status="skipped",
            result_content=None,
            toolcall_arguments={"command": ["git", "status"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertTrue(result)
        self.group_chat.send_if_exists.assert_called_once()

    async def test_allow_git_command_without_unanswered_issues(self):
        """测试没有未解答issue时允许git命令。"""
        self.issue_manager.has_unanswered_issues.return_value = False

        result = await self.plugin.on_tool_result(
            tool_name="process_create",
            tool_index=0,
            status="skipped",
            result_content=None,
            toolcall_arguments={"command": ["git", "status"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertFalse(result)
        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_ignore_non_command_tools(self):
        """测试忽略非命令工具。"""
        self.issue_manager.has_unanswered_issues.return_value = True

        result = await self.plugin.on_tool_result(
            tool_name="read_file",
            tool_index=0,
            status="skipped",
            result_content=None,
            toolcall_arguments={"filepath": "test.txt"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertFalse(result)
        self.agent.message_processor.add_new_message.assert_not_called()
