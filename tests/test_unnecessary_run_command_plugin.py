"""测试UnnecessaryRunCommandPlugin插件。"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from linhai.agent.plugin import UnnecessaryRunCommandPlugin
from linhai.agent.base import RuntimeMessage, FileContentMessage
from linhai.llm import ToolCallMessage
import bashlex
import bashlex.ast


class TestUnnecessaryRunCommandPlugin(unittest.IsolatedAsyncioTestCase):
    """测试UnnecessaryRunCommandPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()
        self.group_chat = MagicMock()

        # 模拟machine_control
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.group_chat.get_members = MagicMock(side_effect=get_members_side_effect)
        self.group_chat.send_if_exists = AsyncMock()
        self.plugin = UnnecessaryRunCommandPlugin(self.group_chat)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_tool_call.assert_called_once_with(
            self.plugin._after_tool_call
        )

    async def test_after_tool_call_not_run_command(self):
        """测试非run_command工具调用。"""
        tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": "test.txt"},
            assert_success=True,
            with_secret=None,
        )
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )
        self.assertIsNone(result)

    async def test_after_tool_call_run_command_failed(self):
        """测试run_command调用失败。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "ls"},
            assert_success=True,
            with_secret=None,
        )
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", False
        )
        self.assertIsNone(result)

    async def test_after_tool_call_no_command(self):
        """测试run_command没有命令参数。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={},
            assert_success=True,
            with_secret=None,
        )
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )
        self.assertIsNone(result)

    async def test_after_tool_call_with_pipeline_allowed(self):
        """测试在管道中的grep命令允许。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "cat file.txt | grep pattern"},
            assert_success=True,
            with_secret=None,
        )

        # 新插件会跳过包含管道的命令
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )

        self.assertIsNone(result)

    async def test_after_tool_call_with_redirect_allowed(self):
        """测试有重定向的cat命令允许。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "cat file.txt > output.txt"},
            assert_success=True,
            with_secret=None,
        )

        # 重定向命令不会被跳过（不包含管道），但如果没有文件参数，也不会警告
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )

        self.assertIsNone(result)

    async def test_after_tool_call_read_file_tracking(self):
        """测试已读取文件跟踪。"""
        # 创建一个模拟的FileContentMessage
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "grep pattern /path/to/read.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_tool_call_read_file_relative_path(self):
        """测试相对路径的已读取文件跟踪。"""
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "test.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "cat test.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)













    async def test_after_tool_call_tail_command(self):
        """测试tail命令拦截。"""
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "tail -10 /path/to/read.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_tool_call_head_command(self):
        """测试head命令拦截。"""
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "head -10 /path/to/read.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_tool_call_awk_command(self):
        """测试awk命令拦截。"""
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "awk '{print \$1}' /path/to/read.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_tool_call_rg_command(self):
        """测试rg命令拦截。"""
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        # 模拟文件存在且过小
        with patch("linhai.agent.plugin.Path.is_file", return_value=True):
            with patch("linhai.agent.plugin.is_small_file", return_value=True):
                tool_call = ToolCallMessage(
                    function_name="run_command",
                    function_arguments={"command": "rg pattern /path/to/read.txt"},
                    assert_success=True,
                    with_secret=None,
                )

                result = await self.plugin._after_tool_call(
                    self.agent, tool_call, "result", True
                )

        # 第一次警告
        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("警告：检测到使用命令查看已读取文件", result.message)
        self.assertEqual(self.plugin.warning_count, 1)


# 以下测试针对已删除的函数，暂时注释掉
# class TestHelperFunctions(unittest.TestCase):
#     """测试辅助函数。"""
# 
#     def test_get_children(self):
#         """测试get_children函数。"""
#         from linhai.agent.plugin import get_children
# 
#         # 测试compound节点
#         mock_compound = MagicMock(spec=bashlex.ast.node)
#         mock_compound.kind = "compound"
#         mock_compound.list = ["child1", "child2"]
# 
#         result = get_children(mock_compound)
#         self.assertEqual(result, ["child1", "child2"])
# 
#         # 测试command节点
#         mock_command = MagicMock(spec=bashlex.ast.node)
#         mock_command.kind = "command"
#         mock_command.parts = ["part1", "part2"]
# 
#         result = get_children(mock_command)
#         self.assertEqual(result, ["part1", "part2"])
# 
#         # 测试其他节点
#         mock_other = MagicMock(spec=bashlex.ast.node)
#         mock_other.kind = "word"
# 
#         result = get_children(mock_other)
#         self.assertEqual(result, [])
# 
#     @patch("bashlex.parse")
#     def test_should_block_command_with_files(self, mock_parse):
#         """测试should_block_command_with_files函数。"""
#         from linhai.agent.plugin import should_block_command_with_files
# 
#         read_files = {Path("/path/to/file.txt").resolve()}
# 
#         # 创建模拟的AST节点
#         mock_node = MagicMock(spec=bashlex.ast.node)
#         mock_node.kind = "command"
# 
#         mock_word1 = MagicMock(spec=bashlex.ast.node)
#         mock_word1.kind = "word"
#         mock_word1.word = "grep"
# 
#         mock_word2 = MagicMock(spec=bashlex.ast.node)
#         mock_word2.kind = "word"
#         mock_word2.word = "pattern"
# 
#         mock_word3 = MagicMock(spec=bashlex.ast.node)
#         mock_word3.kind = "word"
#         mock_word3.word = "/path/to/file.txt"
# 
#         mock_node.parts = [mock_word1, mock_word2, mock_word3]
# 
#         mock_parse.return_value = [mock_node]
# 
#         result = should_block_command_with_files(
#             "grep pattern /path/to/file.txt", read_files
#         )
#         self.assertTrue(result)
# 
#     def test_analyze_command_parts_for_head_tail(self):
#         """测试_analyze_command_parts函数对head和tail命令的解析。"""
#         from linhai.agent.plugin import _analyze_command_parts, get_children
#         import bashlex
#         from pathlib import Path
#         
#         read_files = {Path("/path/to/read.txt").resolve()}
#         
#         # 测试head命令
#         cmd_head = "head -10 /path/to/read.txt"
#         parts_head = bashlex.parse(cmd_head)
#         node_head = parts_head[0]
#         
#         cmd_name, has_redirect, accesses_read_file = _analyze_command_parts(node_head, read_files)
#         print(f"head命令解析结果: cmd_name={cmd_name}, has_redirect={has_redirect}, accesses_read_file={accesses_read_file}")
#         
#         # 断言head命令应该检测到文件访问
#         self.assertEqual(cmd_name, "head")
#         self.assertFalse(has_redirect)
#         self.assertTrue(accesses_read_file)
#         
#         # 测试tail命令
#         cmd_tail = "tail -10 /path/to/read.txt"
#         parts_tail = bashlex.parse(cmd_tail)
#         node_tail = parts_tail[0]
#         
#         cmd_name, has_redirect, accesses_read_file = _analyze_command_parts(node_tail, read_files)
#         print(f"tail命令解析结果: cmd_name={cmd_name}, has_redirect={has_redirect}, accesses_read_file={accesses_read_file}")
#         
#         # 断言tail命令应该检测到文件访问
#         self.assertEqual(cmd_name, "tail")
#         self.assertFalse(has_redirect)
#         self.assertTrue(accesses_read_file)
#         
#         # 测试grep命令作为对比
#         cmd_grep = "grep pattern /path/to/read.txt"
#         parts_grep = bashlex.parse(cmd_grep)
#         node_grep = parts_grep[0]
#         
#         cmd_name, has_redirect, accesses_read_file = _analyze_command_parts(node_grep, read_files)
#         print(f"grep命令解析结果: cmd_name={cmd_name}, has_redirect={has_redirect}, accesses_read_file={accesses_read_file}")
#         
#         # 断言grep命令应该检测到文件访问
#         self.assertEqual(cmd_name, "grep")
#         self.assertFalse(has_redirect)
#         self.assertTrue(accesses_read_file)


if __name__ == "__main__":
    unittest.main()
