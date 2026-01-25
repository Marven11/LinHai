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
        lifecycle.register_on_tool_result.assert_called_once_with(
            self.plugin.on_tool_result
        )

    async def test_on_tool_result_failed(self):
        """测试工具失败时启动subagent。"""
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
        self.group_chat.get_members.side_effect = lambda member_type, member_class=None: mock_subagent_manager if member_type == "subagent_manager" else mock_agent

        # 调用on_tool_result模拟工具失败
        result = await self.plugin.on_tool_result(
            tool_name="test_tool",
            tool_index=0,
            status="failed",
            result_content="测试错误",
            toolcall_arguments={},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )

        self.assertIsNone(result)
        self.group_chat.send_if_exists.assert_called_once()
        call_args = self.group_chat.send_if_exists.call_args
        self.assertEqual(call_args[0][0], "ui_log")
        self.assertEqual(call_args[0][1].level, "WARNING")
        mock_subagent_manager.create_subagent.assert_called_once()

    async def test_on_tool_result_conflict(self):
        """测试工具冲突时启动subagent。"""
        # 注意：on_tool_result回调目前只处理失败状态，冲突状态需要额外处理
        # 这里暂时留空，等待violation_checker.py实现冲突处理
        pass

    async def test_check_violations_success(self):
        """测试规则检查成功启动subagent。"""
        mock_subagent_manager = AsyncMock()
        mock_subagent_manager.create_subagent = AsyncMock()

        full_response = "测试回答内容"
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
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
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
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
        tool_call = ToolCallMessage(
            function_name="test_tool",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        error = "测试错误"

        with self.assertRaises(Exception) as context:
            await self.plugin._check_violations(
                mock_subagent_manager, full_response, tool_call, error
            )

        self.assertEqual(str(context.exception), "测试异常")


if __name__ == "__main__":
    unittest.main()
