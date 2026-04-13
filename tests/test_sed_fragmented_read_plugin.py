"""测试SedFragmentedReadPlugin插件。"""

import asyncio
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.agent.messages import RuntimeMessage
from linhai.plugin.file_operations import SedFragmentedReadPlugin
from linhai.tool.base import ToolCallResultMessage, ToolResultSuccess


def _make_message(content: str) -> ToolCallResultMessage:
    return ToolCallResultMessage(
        tool_name="read_file_with_sed",
        tool_index=0,
        result=ToolResultSuccess(content=content),
        toolcall_arguments={"filepath": "/tmp/test.py", "expression": "1,10p"},
    )


class TestSedFragmentedReadPlugin(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registry.send_if_exists = AsyncMock(return_value=None)
        self.mock_machine_control = MagicMock()
        self.mock_machine_control.target_machine = "master_host"

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "machine_control":
                return self.mock_machine_control
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = MagicMock(
            side_effect=get_member_typechecked_side_effect
        )
        self.plugin = SedFragmentedReadPlugin(self.registry)

    def test_init(self):
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertEqual(self.plugin._records, {})
        self.assertEqual(self.plugin._count, {})

    def test_register(self):
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_toolcall.register.assert_called_once_with(
            self.plugin.after_toolcall
        )

    def test_ignores_non_master_host(self):
        self.mock_machine_control.target_machine = "other_host"
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)
        self.mock_machine_control.target_machine = "master_host"

    def test_ignores_failed_status(self):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "failed",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    def test_ignores_non_sed_tool(self):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "write_file",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    def test_ignores_missing_filepath(self):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    def test_ignores_none_message(self):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                None,
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    def test_ignores_non_tool_call_result_message(self):
        mock_msg = MagicMock()
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                mock_msg,
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=1500)
    def test_large_token_resets_count(self, mock_tokens):
        self.plugin._count["/tmp/test.py"] = 2
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("x" * 5000),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 0)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_first_read_no_overlap_no_warning(self, mock_tokens):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_second_read_with_overlap_count_1_no_trigger(self, mock_tokens):
        content_a = "line1\nline2\nline3\n"
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_a),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        content_b = "line2\nline3\nline4\n"
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_b),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)
        # 第一次读取后计数应为0（无重叠），第二次有重叠，计数应为1
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 1)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_third_read_with_overlap_triggers(self, mock_tokens):
        content_a = "line1\nline2\nline3\n"
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_a),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        content_b = "line2\nline3\nline4\n"
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_b),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        content_c = "line3\nline4\nline5\n"
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_c),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        # 第三次读取后计数=2，小于3，不触发警告
        self.assertIsNone(result)
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 2)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_read_file_resets_count(self, mock_tokens):
        content_a = "line1\nline2\nline3\n"
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_a),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        content_b = "line2\nline3\nline4\n"
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(content_b),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)
        # 第一次读取后计数应为0，第二次有重叠，计数应为1
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 1)
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file",
                0,
                "success",
                None,
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 0)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_no_overlap_no_count(self, mock_tokens):
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("aaa\nbbb\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("ccc\nddd\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)
        # 两次读取无重叠，计数应为0
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 0)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_different_files_tracked_separately(self, mock_tokens):
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/a.py"},
                None,
                False,
            )
        )
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("line1\nline2\n"),
                {"filepath": "/tmp/b.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_cleanup_removes_old_records(self, mock_tokens):
        old_time = time.time() - 400
        self.plugin._records["/tmp/test.py"] = [({"line1", "line2"}, old_time)]
        self.plugin._count["/tmp/test.py"] = 5
        asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message("new\nlines\n"),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        # 清理后应该只剩下新的记录，新记录与旧记录无重叠（旧记录已清理），计数应为0
        self.assertEqual(self.plugin._count.get("/tmp/test.py", 0), 0)

    @patch("linhai.utils.tokenizer.count_tokens", return_value=50)
    def test_empty_content_lines_ignored(self, mock_tokens):
        result = asyncio.run(
            self.plugin.after_toolcall(
                "read_file_with_sed",
                0,
                "success",
                _make_message(""),
                {"filepath": "/tmp/test.py"},
                None,
                False,
            )
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
