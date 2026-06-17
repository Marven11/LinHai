import unittest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
import tempfile
import shutil
import asyncio

from linhai.plugin import (
    FileOperationPermissionPlugin,
    FileReadWriteConflictPlugin,
    UnnecessarySedReadPlugin,
    UnnecessaryRunCommandPlugin,
    DuplicateFileReadPlugin,
)
from linhai.registry import Registry
from linhai.tool.base import (
    ToolCallResultMessage,
    FileContentToolResult,
    SuccessfulToolResult,
    FailedToolResult,
)
from linhai.base import ToolCallMessage
from linhai.config import ToolConfig, FileOperationRule
from linhai.agent.lifecycle import AfterToolcallResult
from linhai.agent.messages import RuntimeMessage


def _make_file_msg(filepath="", content="", show_line_numbers=False, **kwargs):
    return ToolCallResultMessage(
        tool_name="read_file",
        tool_index=0,
        result=FileContentToolResult(
            filepath=filepath,
            content=content,
            show_line_numbers=show_line_numbers,
            **kwargs,
        ),
        toolcall_arguments={},
    )


class TestFileOperationPermissionPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.pwd = Path.cwd()
        self.temp_dir = tempfile.mkdtemp(dir=self.pwd)
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("测试内容\n第二行\n第三行", encoding="utf-8")
        self.tool_config = MagicMock(spec=ToolConfig)
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"

    def _make_plugin(self, tool_config=None):
        config = tool_config or self.tool_config
        plugin = FileOperationPermissionPlugin(self.registry, config)
        plugin._get_pwd = lambda: self.pwd
        plugin._is_master_host = lambda: True
        return plugin

    def tearDown(self):
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    async def test_check_permission_allow_read(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_block_write(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = plugin.check_permission("write", str(self.test_file))
        self.assertFalse(result)

    async def test_check_permission_read_write_operation(self):
        rule = FileOperationRule(
            operation="READ_WRITE", pattern="**/*.txt", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("read", str(self.test_file)))
        self.assertFalse(plugin.check_permission("write", str(self.test_file)))

    async def test_check_permission_with_relative_path(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        relative_path = self.test_file.relative_to(self.pwd)
        result = plugin.check_permission("read", str(relative_path))
        self.assertTrue(result)

    async def test_check_permission_default_rule_allow(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_default_rule_block(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "BLOCK"
        plugin = self._make_plugin()
        result = plugin.check_permission("read", str(self.test_file))
        self.assertFalse(result)

    async def test_before_tool_call_read_file_allowed(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_before_tool_call_write_file_blocked(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="write_file",
            toolcall_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("用户设置禁止你写入", result.content)

    async def test_before_tool_call_unsupported_tool(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="unsupported_tool",
            toolcall_arguments={},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_check_permission_absolute_path_block(self):
        rule = FileOperationRule(
            operation="READ", pattern="/tmp/fobidden/**", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("read", "/tmp/fobidden/test.txt"))
        self.assertTrue(plugin.check_permission("read", "/tmp/other/test.txt"))

    async def test_check_permission_absolute_path_allow_only(self):
        rule = FileOperationRule(
            operation="READ", pattern="/tmp/allowed/**", action="ALLOW"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "BLOCK"
        plugin = self._make_plugin()
        self.assertTrue(plugin.check_permission("read", "/tmp/allowed/test.txt"))
        self.assertFalse(plugin.check_permission("read", "/tmp/other/test.txt"))

    async def test_check_permission_absolute_path_write_block(self):
        rule = FileOperationRule(
            operation="WRITE", pattern="/tmp/readonly/**", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        self.tool_config.file_operation_default_rule = "ALLOW"
        plugin = self._make_plugin()
        self.assertFalse(plugin.check_permission("write", "/tmp/readonly/test.txt"))
        self.assertTrue(plugin.check_permission("read", "/tmp/readonly/test.txt"))

    async def test_before_tool_call_skip_non_master_host(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        plugin._is_master_host = lambda: False
        result = await plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_block_message_contains_chinese_and_filepath(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        result = await plugin.before_tool_call(
            tool_name="write_file",
            toolcall_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("用户设置禁止你写入", result.content)
        self.assertIn(str(self.test_file), result.content)

    async def test_mixed_read_write_in_same_generation(self):
        rule = FileOperationRule(
            operation="READ_WRITE", pattern="**/*.txt", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        plugin = self._make_plugin()
        read_result = await plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(read_result, FailedToolResult)
        self.assertIn("用户设置禁止你读取", read_result.content)

        write_result = await plugin.before_tool_call(
            tool_name="write_file",
            toolcall_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(write_result, FailedToolResult)
        self.assertIn("用户设置禁止你写入", write_result.content)


class TestFileReadWriteConflictPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.plugin = FileReadWriteConflictPlugin(self.registry)
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("测试内容\n第二行\n第三行", encoding="utf-8")
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

    def tearDown(self):
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    async def test_read_then_write_same_file_should_warn(self):
        self.registry.get_member_typechecked.return_value = self.mock_machine_control

        await self.plugin.before_message_generation()
        read_tool_call = ToolCallMessage(
            function_name="read_file",
            function_arguments={"filepath": str(self.test_file)},
            assert_success=True,
            with_secret={"in_arguments": [], "in_result": []},
        )
        read_result = SuccessfulToolResult(
            content="文件内容",
            original_tool_call=read_tool_call,
            with_secret={"in_arguments": [], "in_result": []},
        )
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            read_result.content,
            read_tool_call.function_arguments,
            read_tool_call.with_secret,
            False,
        )
        self.assertIsNone(result)

        write_tool_call = ToolCallMessage(
            function_name="write_file",
            function_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            assert_success=True,
            with_secret={"in_arguments": [], "in_result": []},
        )
        write_result = SuccessfulToolResult(
            content="写入成功",
            original_tool_call=write_tool_call,
            with_secret={"in_arguments": [], "in_result": []},
        )
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            write_result.content,
            write_tool_call.function_arguments,
            write_tool_call.with_secret,
            False,
        )
        self.assertIsNotNone(result)
        self.assertIn("警告", result.replacement.message)
        self.assertIn(str(self.test_file), result.replacement.message)
        self.assertEqual(len(result.user_notices), 1)
        self.assertIn(str(self.test_file), result.user_notices[0])

    async def test_read_then_write_different_file_should_not_warn(self):
        self.registry.get_member_typechecked.return_value = self.mock_machine_control

        await self.plugin.before_message_generation()
        other_file = Path(self.temp_dir) / "other.txt"
        other_file.write_text("其他文件内容", encoding="utf-8")
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            "文件内容",
            {"filepath": str(self.test_file)},
            [],
            False,
        )
        self.assertIsNone(result)
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            "写入成功",
            {"filepath": str(other_file), "content": "新内容", "override": True},
            [],
            False,
        )
        self.assertIsNone(result)

    async def test_not_master_host_should_not_check(self):
        self.mock_machine_control.target_machine = "other_host"
        self.registry.get_member_typechecked.return_value = self.mock_machine_control

        await self.plugin.before_message_generation()
        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            "文件内容",
            {"filepath": str(self.test_file)},
            [],
            False,
        )
        self.assertIsNone(result)
        result = await self.plugin.after_toolcall(
            "write_file",
            0,
            "success",
            "写入成功",
            {
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            [],
            False,
        )
        self.assertIsNone(result)

    async def test_various_read_write_tools(self):
        self.registry.get_member_typechecked.return_value = self.mock_machine_control
        await self.plugin.before_message_generation()

        result = await self.plugin.after_toolcall(
            "read_file",
            0,
            "success",
            "第一行",
            {
                "filepath": str(self.test_file),
                "expression": "1p",
            },
            [],
            False,
        )
        self.assertIsNone(result)

        result = await self.plugin.after_toolcall(
            "replace_file_content",
            0,
            "success",
            "替换成功",
            {
                "filepath": str(self.test_file),
                "old": "测试内容",
                "new": "新内容",
            },
            [],
            False,
        )
        self.assertIsNotNone(result)

    async def test_failed_tool_call_should_be_ignored(self):
        self.registry.get_member_typechecked.return_value = self.mock_machine_control
        await self.plugin.before_message_generation()
        result = await self.plugin.after_toolcall(
            "read_file", 0, "failed", None, {"filepath": str(self.test_file)}, [], False
        )
        self.assertIsNone(result)
        self.assertEqual(len(self.plugin.read_files), 0)

    def test_before_message_generation_clears_list(self):
        self.plugin.read_files = {"/path/to/file1.txt", "/path/to/file2.txt"}
        self.assertEqual(len(self.plugin.read_files), 2)
        asyncio.run(self.plugin.before_message_generation())
        self.assertEqual(len(self.plugin.read_files), 0)


class TestUnnecessarySedReadPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        self.registry.send_if_exists = AsyncMock(return_value=None)

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])

        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )

        self.plugin = UnnecessarySedReadPlugin(self.registry)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_large_result(self, mock_open, mock_path):
        mock_message = MagicMock()
        mock_message.to_llm_message.return_value = {"content": "test result"}
        mock_path.return_value.is_file.return_value = True

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                mock_message,
                {"filepath": "./test.py"},
                None,
                False,
            )
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn("警告：检测到不必要的sed读取", result.replacement.message)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_file_not_exists(self, mock_open, mock_path):
        mock_message = MagicMock()
        mock_message.to_llm_message.return_value = {"content": "test result"}
        mock_path.return_value.is_file.return_value = False

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                mock_message,
                {"filepath": "./test.py"},
                None,
                False,
            )
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn("警告：检测到不必要的sed读取", result.replacement.message)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\n")
    def test_first_call(self, mock_open, mock_path):
        mock_message = MagicMock()
        mock_message.to_llm_message.return_value = {"content": "test result"}
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                mock_message,
                {"filepath": "./test.py"},
                None,
                False,
            )
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn("警告：检测到不必要的sed读取", result.replacement.message)
        self.assertEqual(self.plugin.warning_count, 1)


class TestDuplicateFileReadPlugin(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        self.registry.send_if_exists = AsyncMock(return_value=None)

        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])

        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )

        self.plugin = DuplicateFileReadPlugin(self.registry)

    @patch("pathlib.Path")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n"
    )
    def test_allows_sed_when_no_full_read(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        self.agent.message_processor.get_messages.return_value = []

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                MagicMock(),
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("pathlib.Path")
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"line1\\nline2\\nline3\\n"
    )
    def test_blocks_read_file_when_identical(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        file_content_message = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [file_content_message]

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("第一次警告", result.warnings[0].message)

        self.registry.send_if_exists.reset_mock()

        result2 = asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNotNone(result2)
        self.assertIsInstance(result2, AfterToolcallResult)
        self.assertIn("错误：你已经读取过文件", result2.replacement.message)
        self.assertEqual(result2.user_notices, ["模型第二次重复读取相同文件，已阻止"])

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_allows_first_read(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        self.agent.message_processor.get_messages.return_value = []

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_allows_different_content(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        old_file_content = _make_file_msg(
            absolute_path, "old line1\nold line2\nold line3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [old_file_content]

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_ignores_on_non_master_host(self, mock_open, mock_path):
        self.mock_machine_control.target_machine = "other_host"

        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        old_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [old_file_content]

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNone(result)

        self.mock_machine_control.target_machine = "master_host"

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_handles_multiple_messages_latest_same(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        old_content1 = _make_file_msg(
            filepath=absolute_path, content="old content", show_line_numbers=False
        )
        old_content2 = _make_file_msg(
            filepath=absolute_path, content="different content", show_line_numbers=False
        )
        latest_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [
            old_content1,
            old_content2,
            latest_content,
        ]

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("第一次警告", result.warnings[0].message)

        self.registry.send_if_exists.reset_mock()

        result2 = asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNotNone(result2)
        self.assertIsInstance(result2, AfterToolcallResult)
        self.assertIn("错误：你已经读取过文件", result2.replacement.message)
        self.assertEqual(result2.user_notices, ["模型第二次重复读取相同文件，已阻止"])

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_handles_multiple_messages_latest_different(self, mock_open, mock_path):
        mock_path.return_value.is_file.return_value = True
        absolute_path = "/absolute/path/test.py"
        mock_path.return_value.resolve.return_value = Path(absolute_path)

        old_content1 = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        old_content2 = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )
        latest_content = _make_file_msg(
            absolute_path, "different content", show_line_numbers=False
        )
        self.agent.message_processor.get_messages.return_value = [
            old_content1,
            old_content2,
            latest_content,
        ]

        new_file_content = _make_file_msg(
            absolute_path, "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_handles_resolve_error_current_path(self, mock_open, mock_path):
        mock_path.return_value.resolve.side_effect = OSError("Permission denied")

        new_file_content = _make_file_msg(
            "/some/path/test.py", "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                new_file_content,
                {"filepath": "/some/file.txt"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("pathlib.Path")
    @patch("builtins.open", new_callable=mock_open, read_data=b"line1\nline2\nline3\n")
    def test_handles_resolve_error_historical_path(self, mock_open, mock_path):
        absolute_path = "/absolute/path/test.py"

        current_path_instance = MagicMock(spec=Path)
        current_path_instance.resolve.return_value = Path(absolute_path)

        bad_path_instance = MagicMock(spec=Path)
        bad_path_instance.resolve.side_effect = OSError("Bad path")

        good_path_instance = MagicMock(spec=Path)
        good_path_instance.resolve.return_value = Path(absolute_path)

        def path_side_effect(path_str):
            if path_str == "/bad/path":
                return bad_path_instance
            elif path_str == "/absolute/path/test.py" or path_str == "./test.py":
                return good_path_instance
            else:
                return current_path_instance

        mock_path.side_effect = path_side_effect

        bad_message = _make_file_msg(
            filepath="/bad/path", content="old content", show_line_numbers=False
        )

        good_message = _make_file_msg(
            filepath="/absolute/path/test.py",
            content="line1\nline2\nline3\n",
            show_line_numbers=False,
        )

        self.agent.message_processor.get_messages.return_value = [
            bad_message,
            good_message,
        ]

        new_file_content = _make_file_msg(
            "/absolute/path/test.py", "line1\nline2\nline3\n", show_line_numbers=False
        )

        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                new_file_content,
                {"filepath": absolute_path},
                None,
                False,
            )
        )
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("第一次警告", result.warnings[0].message)


class TestUnnecessaryRunCommandPlugin(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()
        self.registry = MagicMock()

        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "agent":
                return self.agent
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )
        self.registry.send_if_exists = AsyncMock()
        self.plugin = UnnecessaryRunCommandPlugin(self.registry)

    async def test_after_toolcall_not_process_create(self):
        result = await self.plugin.after_toolcall(
            tool_name="read_file",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"filepath": "test.txt"},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_process_create_failed(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="failed",
            message="result",
            toolcall_arguments={"command": ["ls"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_no_command(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_with_pipeline_allowed(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"command": ["cat", "file.txt", "|", "grep", "pattern"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_with_redirect_allowed(self):
        result = await self.plugin.after_toolcall(
            tool_name="process_create",
            tool_index=0,
            status="success",
            message="result",
            toolcall_arguments={"command": ["cat", "file.txt", ">", "output.txt"]},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        self.assertIsNone(result)

    async def test_after_toolcall_read_file_tracking(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["grep", "pattern", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_read_file_relative_path(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "test.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={"command": ["cat", "test.txt"]},
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_tail_command(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["tail", "-10", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_head_command(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["head", "-10", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_awk_command(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["awk", "{print $1}", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)

    async def test_after_toolcall_rg_command(self):
        mock_file_msg = MagicMock(spec=ToolCallResultMessage)
        mock_file_msg.filepath = "/path/to/read.txt"

        self.agent.message_processor.get_messages.return_value = [mock_file_msg]

        with patch("linhai.plugin.file_operations.is_existing_file", return_value=True):
            with patch(
                "linhai.plugin.file_operations.is_already_read",
                AsyncMock(return_value=True),
            ):
                result = await self.plugin.after_toolcall(
                    tool_name="process_create",
                    tool_index=0,
                    status="success",
                    message="result",
                    toolcall_arguments={
                        "command": ["rg", "pattern", "/path/to/read.txt"]
                    },
                    with_secret=None,
                    is_tool_failed_duplicated_error=False,
                )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertIn(
            "警告：检测到不必要的process_create用于读取已读文件",
            result.replacement.message,
        )
        self.assertEqual(self.plugin.warning_count, 1)


if __name__ == "__main__":
    unittest.main()
