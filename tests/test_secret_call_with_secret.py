"""call_with_secret工具和SecretToolsetPlugin的单元测试"""

import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from linhai.secret import (
    SecretInfo,
    _create_call_with_secret_toolset,
    SecretToolsetPlugin,
    _CALL_WITH_SECRET_RULE,
)
from linhai.tool.base import SuccessfulToolResult, FailedToolResult, ToolSet
from linhai.agent.messages import RuntimeMessage


def _make_secrets_dict() -> dict[str, SecretInfo]:
    return {
        "SECRET1": {
            "value": "secret-value-1",
            "description": "test secret 1",
            "disabled_in_toolcall_argument": False,
        },
        "SECRET2": {
            "value": "secret-value-2",
            "description": "test secret 2",
            "disabled_in_toolcall_argument": False,
        },
        "DISABLED_SECRET": {
            "value": "disabled-value",
            "description": "disabled secret",
            "disabled_in_toolcall_argument": True,
        },
    }


class FakeRegistry:
    def __init__(self):
        self.members = {}

    def register_member(self, name, obj):
        self.members[name] = obj

    def get_member_typechecked(self, name, _type=None):
        if name in self.members:
            return self.members[name]
        raise RuntimeError(f"Member {name} not found")


class TestCreateCallWithSecretToolset(unittest.TestCase):
    def test_toolset_has_call_with_secret(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)
        self.assertIsInstance(toolset, ToolSet)
        self.assertTrue(toolset.has_tool("call_with_secret"))

    def test_call_with_secret_replaces_and_calls(self):
        import tempfile
        import os

        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "secret_intercepted").mkdir()

        mock_tool_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.get_content.return_value = "result with secret-value-1"
        mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        registry.members["tool_manager"] = mock_tool_manager
        registry.members["conversation_folder"] = tmpdir

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["SECRET1"],
            )
        )
        loop.close()

        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertNotIn("secret-value-1", result.content)
        mock_tool_manager.process_tool_call.assert_called_once()

        import shutil

        shutil.rmtree(tmpdir)

    def test_call_with_secret_key_not_found(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["NONEXISTENT"],
            )
        )
        loop.close()

        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("NONEXISTENT", result.content)

    def test_call_with_secret_disabled_key(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["DISABLED_SECRET"],
            )
        )
        loop.close()

        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("DISABLED_SECRET", result.content)

    def test_call_with_secret_placeholder_format_error(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["<$SECRET1$>"],
            )
        )
        loop.close()

        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("格式错误", result.content)

    def test_call_with_secret_no_content_result(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        mock_tool_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.get_content.return_value = None
        mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        registry.members["tool_manager"] = mock_tool_manager

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["SECRET1"],
            )
        )
        loop.close()

        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertEqual(result.content, "工具执行完成，无文本输出")

    def test_call_with_secret_unlisted_secret_in_result(self):
        import tempfile
        import shutil

        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)

        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "secret_intercepted").mkdir()

        mock_tool_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.get_content.return_value = "result with secret-value-2"
        mock_tool_manager.process_tool_call = AsyncMock(return_value=mock_result)
        registry.members["tool_manager"] = mock_tool_manager
        registry.members["conversation_folder"] = tmpdir

        func = toolset.get_tool("call_with_secret")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            func(
                tool_name="test_tool",
                tool_arguments={"key": "val"},
                with_secret=["SECRET1"],
            )
        )
        loop.close()

        self.assertIsInstance(result, SuccessfulToolResult)
        self.assertIn("SECRET2", result.content)

        shutil.rmtree(tmpdir)


class TestSecretToolsetPlugin(unittest.TestCase):
    def _make_plugin(self):
        registry = FakeRegistry()
        secrets_dict = _make_secrets_dict()
        plugin = SecretToolsetPlugin(registry, secrets_dict)
        return plugin, registry

    def test_custom_format_disables_toolset(self):
        plugin, registry = self._make_plugin()

        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_custom_toolcall_format.return_value = True
        mock_agent.get_current_model.return_value = mock_llm

        mock_tool_manager = MagicMock()
        mock_system_message = MagicMock()

        registry.members["agent"] = mock_agent
        registry.members["tool_manager"] = mock_tool_manager
        registry.members["system_message"] = mock_system_message

        loop = asyncio.new_event_loop()
        loop.run_until_complete(plugin.before_message_generation())
        loop.close()

        mock_tool_manager.set_toolset_enabled.assert_called_once_with(
            "secret_wrapper", False
        )
        mock_system_message.remove_rule.assert_called_once_with("CALL WITH SECRET")
        mock_system_message.add_rule.assert_not_called()

    def test_openai_format_enables_toolset(self):
        plugin, registry = self._make_plugin()

        mock_agent = MagicMock()
        mock_llm = MagicMock()
        mock_llm.get_custom_toolcall_format.return_value = False
        mock_agent.get_current_model.return_value = mock_llm

        mock_tool_manager = MagicMock()
        mock_system_message = MagicMock()

        registry.members["agent"] = mock_agent
        registry.members["tool_manager"] = mock_tool_manager
        registry.members["system_message"] = mock_system_message

        loop = asyncio.new_event_loop()
        loop.run_until_complete(plugin.before_message_generation())
        loop.close()

        mock_tool_manager.set_toolset_enabled.assert_called_once_with(
            "secret_wrapper", True
        )
        mock_system_message.remove_rule.assert_called_once_with("CALL WITH SECRET")
        mock_system_message.add_rule.assert_called_once()
        call_args = mock_system_message.add_rule.call_args
        self.assertEqual(call_args[0][0], "CALL WITH SECRET")


class TestCallWithSecretRule(unittest.TestCase):
    def test_rule_has_format_placeholder(self):
        self.assertIn("{secrets_list}", _CALL_WITH_SECRET_RULE)

    def test_rule_format(self):
        formatted = _CALL_WITH_SECRET_RULE.format(secrets_list="test keys")
        self.assertIn("test keys", formatted)
        self.assertNotIn("{secrets_list}", formatted)


if __name__ == "__main__":
    unittest.main()
