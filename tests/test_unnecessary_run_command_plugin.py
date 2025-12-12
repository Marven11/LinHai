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
        self.agent.message_processor.append_message = MagicMock()
        self.group_chat = MagicMock()
        self.group_chat.get_members = MagicMock(return_value=self.agent)
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
        )
        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )
        self.assertIsNone(result)

    async def test_after_tool_call_simple_sed_blocked(self):
        """测试直接使用sed命令被拦截。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "sed -n '1,10p' file.txt"},
        )

        # 模拟没有已读取的文件
        with patch.object(self.plugin, "_get_read_files", return_value=set()):
            result = await self.plugin._after_tool_call(
                self.agent, tool_call, "result", True
            )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        assert result is not None  # 帮助类型检查器
        self.assertIn("禁止直接使用sed命令", result.message)

    async def test_after_tool_call_simple_grep_blocked(self):
        """测试直接使用grep命令被拦截。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "grep pattern file.txt"},
        )

        with patch.object(self.plugin, "_get_read_files", return_value=set()):
            result = await self.plugin._after_tool_call(
                self.agent, tool_call, "result", True
            )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)
        assert result is not None  # 帮助类型检查器
        self.assertIn("禁止使用grep命令", result.message)

    async def test_after_tool_call_with_pipeline_allowed(self):
        """测试在管道中的grep命令允许。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "cat file.txt | grep pattern"},
        )

        with patch.object(self.plugin, "_get_read_files", return_value=set()):
            result = await self.plugin._after_tool_call(
                self.agent, tool_call, "result", True
            )

        self.assertIsNone(result)

    async def test_after_tool_call_with_redirect_allowed(self):
        """测试有重定向的cat命令允许。"""
        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "cat file.txt > output.txt"},
        )

        with patch.object(self.plugin, "_get_read_files", return_value=set()):
            result = await self.plugin._after_tool_call(
                self.agent, tool_call, "result", True
            )

        self.assertIsNone(result)

    async def test_after_tool_call_read_file_tracking(self):
        """测试已读取文件跟踪。"""
        # 模拟已读取的文件
        read_file_path = Path("/path/to/read.txt").resolve()
        read_files = {read_file_path}

        # 创建一个模拟的FileContentMessage
        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "grep pattern /path/to/read.txt"},
        )

        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)

    async def test_after_tool_call_read_file_relative_path(self):
        """测试相对路径的已读取文件跟踪。"""
        # 模拟当前目录下的已读取文件
        current_dir = Path.cwd()
        read_file_path = (current_dir / "test.txt").resolve()
        read_files = {read_file_path}

        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "test.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "cat test.txt"},
        )

        result = await self.plugin._after_tool_call(
            self.agent, tool_call, "result", True
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, RuntimeMessage)

    async def test_after_tool_call_different_file_allowed(self):
        """测试访问未读取的文件允许。"""
        # 模拟已读取的文件
        read_file_path = Path("/path/to/read.txt").resolve()
        read_files = {read_file_path}

        mock_file_msg = MagicMock(spec=FileContentMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        tool_call = ToolCallMessage(
            function_name="run_command",
            function_arguments={"command": "grep pattern /path/to/other.txt"},
        )

        with patch.object(self.plugin, "_get_read_files", return_value=read_files):
            result = await self.plugin._after_tool_call(
                self.agent, tool_call, "result", True
            )

        # 应该允许，因为访问的是不同的文件
        self.assertIsNone(result)

    async def test_get_read_files(self):
        """测试获取已读取的文件。"""
        # 创建模拟的FileContentMessage
        mock_msg1 = MagicMock(spec=FileContentMessage)
        mock_msg1.filepath = "/path/to/file1.txt"

        mock_msg2 = MagicMock(spec=FileContentMessage)
        mock_msg2.filepath = "relative/file2.txt"

        mock_msg3 = MagicMock(spec=FileContentMessage)
        mock_msg3.filepath = "/path/to/file1.txt"  # 重复文件

        self.agent.message_processor.get_messages.return_value = [
            mock_msg1,
            mock_msg2,
            mock_msg3,
        ]

        read_files = self.plugin._get_read_files(self.agent)

        # 应该只有2个唯一的文件
        self.assertEqual(len(read_files), 2)

        # 检查路径是否被解析为绝对路径
        for path in read_files:
            self.assertTrue(path.is_absolute())

    def test_generate_warning_message_sed(self):
        """测试生成sed警告消息。"""
        result = self.plugin._generate_warning_message("sed -n '1,10p' file.txt")
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("禁止直接使用sed命令查看文件", result.message)

    def test_generate_warning_message_grep(self):
        """测试生成grep警告消息。"""
        result = self.plugin._generate_warning_message("grep pattern file.txt")
        self.assertIsInstance(result, RuntimeMessage)
        self.assertIn("禁止使用grep命令直接查看文件", result.message)

    def test_generate_warning_message_parse_error(self):
        """测试解析错误的命令。"""
        result = self.plugin._generate_warning_message("invalid | command &")
        self.assertIsInstance(result, RuntimeMessage)
        # 应该有一个默认的消息

    def test_extract_command_name(self):
        """测试从AST节点提取命令名。"""
        # 创建一个模拟的AST节点
        mock_node = MagicMock(spec=bashlex.ast.node)
        mock_node.kind = "command"

        mock_word = MagicMock(spec=bashlex.ast.node)
        mock_word.kind = "word"
        mock_word.word = "grep"

        mock_node.parts = [mock_word]

        forbidden_commands = {"grep", "head", "tail", "cat", "sed"}

        result = self.plugin._extract_command_name(mock_node, forbidden_commands)
        self.assertEqual(result, "grep")

    def test_extract_command_name_not_found(self):
        """测试从AST节点提取不在禁止列表中的命令名。"""
        mock_node = MagicMock(spec=bashlex.ast.node)
        mock_node.kind = "command"

        mock_word = MagicMock(spec=bashlex.ast.node)
        mock_word.kind = "word"
        mock_word.word = "ls"

        mock_node.parts = [mock_word]

        forbidden_commands = {"grep", "head", "tail", "cat", "sed"}

        result = self.plugin._extract_command_name(mock_node, forbidden_commands)
        self.assertIsNone(result)


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数。"""

    def test_get_children(self):
        """测试get_children函数。"""
        from linhai.agent.plugin import get_children

        # 测试compound节点
        mock_compound = MagicMock(spec=bashlex.ast.node)
        mock_compound.kind = "compound"
        mock_compound.list = ["child1", "child2"]

        result = get_children(mock_compound)
        self.assertEqual(result, ["child1", "child2"])

        # 测试command节点
        mock_command = MagicMock(spec=bashlex.ast.node)
        mock_command.kind = "command"
        mock_command.parts = ["part1", "part2"]

        result = get_children(mock_command)
        self.assertEqual(result, ["part1", "part2"])

        # 测试其他节点
        mock_other = MagicMock(spec=bashlex.ast.node)
        mock_other.kind = "word"

        result = get_children(mock_other)
        self.assertEqual(result, [])

    def test_should_block_command_simple(self):
        """测试should_block_command_simple函数。"""
        from linhai.agent.plugin import should_block_command_simple

        # 直接sed命令应该被拦截
        self.assertTrue(should_block_command_simple("sed -n '1,10p' file.txt"))

        # 管道中的sed命令应该允许
        self.assertFalse(should_block_command_simple("cat file.txt | sed 's/old/new/'"))

        # 有重定向的cat命令应该允许
        self.assertFalse(should_block_command_simple("cat file.txt > output.txt"))

        # 无效命令不应该拦截
        self.assertFalse(should_block_command_simple(""))
        self.assertFalse(should_block_command_simple("invalid command"))

    @patch("bashlex.parse")
    def test_should_block_command_with_files(self, mock_parse):
        """测试should_block_command_with_files函数。"""
        from linhai.agent.plugin import should_block_command_with_files

        read_files = {Path("/path/to/file.txt").resolve()}

        # 创建模拟的AST节点
        mock_node = MagicMock(spec=bashlex.ast.node)
        mock_node.kind = "command"

        mock_word1 = MagicMock(spec=bashlex.ast.node)
        mock_word1.kind = "word"
        mock_word1.word = "grep"

        mock_word2 = MagicMock(spec=bashlex.ast.node)
        mock_word2.kind = "word"
        mock_word2.word = "pattern"

        mock_word3 = MagicMock(spec=bashlex.ast.node)
        mock_word3.kind = "word"
        mock_word3.word = "/path/to/file.txt"

        mock_node.parts = [mock_word1, mock_word2, mock_word3]

        mock_parse.return_value = [mock_node]

        result = should_block_command_with_files(
            "grep pattern /path/to/file.txt", read_files
        )
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
