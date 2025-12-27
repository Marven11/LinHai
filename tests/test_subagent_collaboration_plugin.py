"""测试SubAgentCollaborationPlugin"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from linhai.subagent.subagent_types.violation_checker import ViolationCheckerPlugin
from linhai.llm import ToolCallMessage


class TestViolationCheckerPlugin(unittest.IsolatedAsyncioTestCase):
    """测试ViolationCheckerPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages.return_value = []
        self.agent.message_processor.add_new_message = MagicMock()

        self.mock_subagent_manager = MagicMock()
        self.mock_subagent_manager.create_subagent = AsyncMock()

        self.group_chat = MagicMock()

        def get_members_side_effect(member_type, member_class=None):
            _ = member_class  # 使用参数以消除警告
            if member_type == "subagent_manager":
                return self.mock_subagent_manager
            elif member_type == "agent":
                return self.agent
            raise RuntimeError(f"{member_type!r} not exists")

        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)
        self.group_chat.send_if_exists = AsyncMock()

        self.plugin = ViolationCheckerPlugin(self.group_chat)

    async def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_tool_failure.assert_called_once_with(
            self.plugin.tool_failure
        )
        lifecycle.register_tool_conflict.assert_called_once_with(
            self.plugin.tool_conflict
        )

    async def test_tool_failure(self):
        """测试工具失败时启动subagent。"""
        tool_call = ToolCallMessage(function_name="test_tool", function_arguments={})
        error = "测试错误"

        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        self.group_chat.get_members.return_value = mock_subagent_manager

        mock_agent = MagicMock()
        mock_agent.current_answer = MagicMock()
        mock_agent.current_answer.get_current_content = MagicMock(
            return_value="""首先调用一个工具

```json toolcall
{"name": "list_files", "arguments": {"dirpath": "."}}
```

然后调用另一个工具

```json toolcall
{"name": "read_file", "arguments": {"filepath": "test.txt"}}
```"""
        )

        await self.plugin.tool_failure(mock_agent, tool_call, error)

        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")

    async def test_tool_conflict(self):
        """测试工具冲突时启动subagent。"""
        tool_call = ToolCallMessage(function_name="test_tool", function_arguments={})
        conflicting_tools = ["conflicting_tool1", "conflicting_tool2"]

        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()
        self.group_chat.get_members.return_value = mock_subagent_manager

        mock_agent = MagicMock()
        mock_agent.current_answer = MagicMock()
        mock_agent.current_answer.get_current_content = MagicMock(
            return_value="测试回答内容"
        )

        await self.plugin.tool_conflict(mock_agent, tool_call, conflicting_tools)

        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")

    async def test_check_violations_success(self):
        """测试规则检查成功启动subagent。"""
        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()

        full_response = "测试回答内容"
        tool_call = ToolCallMessage(function_name="test_tool", function_arguments={})
        error = "测试错误"

        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, error
        )

        mock_subagent_manager.create_subagent.assert_called_once()
        call_args = mock_subagent_manager.create_subagent.call_args
        self.assertEqual(call_args[1]["agent_type"], "violation_checker")
        self.assertIn("violation_subagent", call_args[1]["name"])

    @patch("asyncio.create_task")
    async def test_check_violations_success_with_patch(self, mock_create_task):
        """测试规则检查成功启动subagent（使用patch）。"""
        _ = mock_create_task  # 使用参数以消除警告
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock()

        full_response = "测试回答内容"
        tool_call = ToolCallMessage(function_name="test_tool", function_arguments={})
        error = "测试错误"

        await self.plugin._check_violations(
            mock_subagent_manager, full_response, tool_call, error
        )

        mock_subagent_manager.create_subagent.assert_called_once()
        call_args = mock_subagent_manager.create_subagent.call_args
        self.assertEqual(call_args[1]["agent_type"], "violation_checker")

    async def test_check_violations_exception_propagation(self):
        """测试规则检查异常传播（fail fast）。"""
        mock_subagent_manager = MagicMock()
        mock_subagent_manager.create_subagent = AsyncMock(
            side_effect=Exception("测试异常")
        )

        full_response = "测试回答内容"
        tool_call = ToolCallMessage(function_name="test_tool", function_arguments={})
        error = "测试错误"

        with self.assertRaises(Exception) as context:
            await self.plugin._check_violations(
                mock_subagent_manager, full_response, tool_call, error
            )

        self.assertEqual(str(context.exception), "测试异常")


if __name__ == "__main__":
    unittest.main()
