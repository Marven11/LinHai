import os
import tempfile
import tokenize
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from linhai.agent.lifecycle import AfterToolcallResult
from linhai.agent.messages import (
    GlobalPrompt,
    PathPrompt,
    RuntimeMessage,
)
from linhai.tool.base import ToolCallResultMessage, FileContentToolResult
from linhai.base import AssistantMessage, SystemMessage, UserMessage
from linhai.plugin.python_chore import (
    PythonCommentCheckerPlugin,
    _extract_comments,
    _get_context_contents,
    _read_file_content,
)


class TestExtractComments(unittest.TestCase):
    def test_single_comment(self):
        source = "x = 1  # hello"
        self.assertEqual(_extract_comments(source), ["# hello"])

    def test_no_comments(self):
        source = "x = 1\ny = 2"
        self.assertEqual(_extract_comments(source), [])

    def test_hash_in_string_not_extracted(self):
        source = 's = "# not a comment"'
        self.assertEqual(_extract_comments(source), [])

    def test_multiline_string_markdown_not_extracted(self):
        source = 'doc = """\n# Heading\nSome text\n"""\nx = 1  # real comment'
        comments = _extract_comments(source)
        self.assertEqual(comments, ["# real comment"])


class TestGetContextContents(unittest.TestCase):
    def test_extracts_user_message(self):
        agent = MagicMock()
        msg = UserMessage("please add # init comment")
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 1)
        self.assertIn("# init comment", contents[0])

    def test_extracts_file_content_message(self):
        agent = MagicMock()
        msg = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath="test.py", content="x = 1  # existing", show_line_numbers=False
            ),
            toolcall_arguments={},
        )
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 1)
        self.assertIn("# existing", contents[0])

    def test_extracts_global_prompt(self):
        agent = MagicMock()
        msg = GlobalPrompt(Path("/tmp/AGENTS.md"))
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 1)

    def test_extracts_path_prompt(self):
        agent = MagicMock()
        msg = PathPrompt(Path("/tmp/AGENTS.md"))
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 1)

    def test_extracts_system_message(self):
        registry = MagicMock()
        msg = SystemMessage(registry)
        agent = MagicMock()
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 1)

    def test_ignores_assistant_message(self):
        agent = MagicMock()
        msg = AssistantMessage("some # comment here")
        agent.message_processor.get_messages.return_value = [msg]
        contents = _get_context_contents(agent)
        self.assertEqual(len(contents), 0)


class _BasePluginTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = AsyncMock()

        self.machine_control = MagicMock()
        self.machine_control.target_machine = "master_host"

        self.registry = MagicMock()

        def get_member(name, cls):
            if name == "agent":
                return self.agent
            if name == "machine_control":
                return self.machine_control
            return None

        self.registry.get_member_typechecked = MagicMock(side_effect=get_member)
        self.plugin = PythonCommentCheckerPlugin(self.registry)

    async def _call_after_toolcall(self, tool_name, args, status="success"):
        return await self.plugin.after_toolcall(
            tool_name=tool_name,
            tool_index=0,
            status=status,
            message=None,
            toolcall_arguments=args,
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )


class TestWriteFileWarning(_BasePluginTest):
    async def test_warns_on_new_comments(self):
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": "x = 1  # hello"},
        )
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("你添加了注释", result.warnings[0].message)


class TestMultilineStringNotComment(_BasePluginTest):
    async def test_no_warn_on_markdown_in_multiline_string(self):
        content = 'doc = """\n# Heading\n"""\nx = 1\n'
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": content},
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestPreservedCommentsNoWarning(_BasePluginTest):
    async def test_no_warn_when_comment_in_file_content(self):
        file_msg = ToolCallResultMessage(
            tool_name="read_file",
            tool_index=0,
            result=FileContentToolResult(
                filepath="test.py", content="x = 1  # existing", show_line_numbers=False
            ),
            toolcall_arguments={},
        )
        self.agent.message_processor.get_messages.return_value = [file_msg]

        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": "x = 1  # existing"},
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestCommentInUserMessageNoWarning(_BasePluginTest):
    async def test_no_warn_when_comment_in_user_message(self):
        user_msg = UserMessage("please add # init at top")
        self.agent.message_processor.get_messages.return_value = [user_msg]

        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": "# init\nx = 1"},
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestMixedCommentsOnlyWarnAgentOnes(_BasePluginTest):
    async def test_only_warns_agent_added_comment(self):
        user_msg = UserMessage("add # user_comment")
        self.agent.message_processor.get_messages.return_value = [user_msg]

        content = "# user_comment\nx = 1  # agent_comment"
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": content},
        )
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("你添加了注释", result.warnings[0].message)


class TestReadFileContent(unittest.TestCase):
    def test_reads_existing_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1")
            f.flush()
            content = _read_file_content(f.name)
        os.unlink(f.name)
        self.assertEqual(content, "x = 1")

    def test_returns_none_for_missing_file(self):
        content = _read_file_content("/nonexistent/path/test.py")
        self.assertIsNone(content)


class TestReplaceFileContent(_BasePluginTest):
    async def test_warns_on_new_comment_in_replace(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1  # added")
            f.flush()
            filepath = f.name
        try:
            result = await self._call_after_toolcall(
                "replace_file_content",
                {"filepath": filepath, "old": "x = 1", "new": "x = 1  # added"},
            )
        finally:
            os.unlink(filepath)
        self.assertIsInstance(result, AfterToolcallResult)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("你添加了注释", result.warnings[0].message)

    async def test_no_warn_when_comment_already_in_old(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1  # kept")
            f.flush()
            filepath = f.name
        try:
            result = await self._call_after_toolcall(
                "replace_file_content",
                {"filepath": filepath, "old": "x = 1  # kept", "new": "x = 1  # kept"},
            )
        finally:
            os.unlink(filepath)
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_no_warn_for_multiline_string_hash(self):
        source = 'MARKDOWN = """\n# Example Markdown\n\nLorem Ipsum\n"""\n'
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(source)
            f.flush()
            filepath = f.name
        try:
            old = 'MARKDOWN = """\n# Example Markdown'
            new = 'MARKDOWN = """\n# Example Markdown Containing Lorem Ipsum'
            result = await self._call_after_toolcall(
                "replace_file_content",
                {"filepath": filepath, "old": old, "new": new},
            )
        finally:
            os.unlink(filepath)
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_no_warn_when_file_missing(self):
        result = await self._call_after_toolcall(
            "replace_file_content",
            {
                "filepath": "/nonexistent/test.py",
                "old": "x = 1",
                "new": "x = 1  # added",
            },
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestNotMasterHost(_BasePluginTest):
    async def test_skips_on_non_master_host(self):
        self.machine_control.target_machine = "other_host"
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": "x = 1  # hello"},
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestNotPyFile(_BasePluginTest):
    async def test_skips_non_py_file(self):
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.js", "content": "// comment"},
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


class TestFailedStatus(_BasePluginTest):
    async def test_skips_on_failed_status(self):
        result = await self._call_after_toolcall(
            "write_file",
            {"filepath": "test.py", "content": "x = 1  # hello"},
            status="failed",
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
