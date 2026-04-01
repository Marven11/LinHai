import tokenize
import unittest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from linhai.plugin.python_chore import (
    PythonCommentCheckerPlugin,
    _extract_comments,
    _get_context_contents,
)
from linhai.agent.base import (
    FileContentMessage,
    GlobalPrompt,
    PathPrompt,
    RuntimeMessage,
)
from linhai.llm import UserMessage, SystemMessage, AssistantMessage


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

    def test_syntax_error_raises(self):
        source = "def foo(:\n"
        with self.assertRaises(tokenize.TokenError):
            _extract_comments(source)


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
        msg = FileContentMessage("test.py", "x = 1  # existing", False)
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
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("# hello", call_args[0].message)


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
        file_msg = FileContentMessage("test.py", "x = 1  # existing", False)
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
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        msg = call_args[0]
        self.assertIsInstance(msg, RuntimeMessage)
        self.assertIn("# agent_comment", msg.message)
        self.assertNotIn("# user_comment", msg.message)


class TestReplaceFileContent(_BasePluginTest):
    async def test_warns_on_new_comment_in_replace(self):
        result = await self._call_after_toolcall(
            "replace_file_content",
            {
                "filepath": "test.py",
                "old": "x = 1",
                "new": "x = 1  # added",
            },
        )
        self.assertIsNone(result)
        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIn("# added", call_args[0].message)

    async def test_no_warn_when_comment_already_in_old(self):
        result = await self._call_after_toolcall(
            "replace_file_content",
            {
                "filepath": "test.py",
                "old": "x = 1  # kept",
                "new": "x = 1  # kept",
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


class TestRegister(unittest.TestCase):
    def test_register(self):
        registry = MagicMock()
        plugin = PythonCommentCheckerPlugin(registry)
        lifecycle = MagicMock()
        plugin.register(lifecycle)
        lifecycle.register_after_toolcall.assert_called_once_with(plugin.after_toolcall)
