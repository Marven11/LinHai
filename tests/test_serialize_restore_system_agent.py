import unittest
from unittest.mock import Mock

from linhai.base import SystemMessage
from linhai.agent.messages.runtime import RuntimeMessage
from linhai.agent.messages.file_content import DynamicFileContentMessage
from linhai.agent.planning import PlanningPromptMessage
from pathlib import Path
import json


class TestRuntimeMessageSerialization(unittest.TestCase):
    def test_roundtrip(self):
        original = RuntimeMessage("system notice")
        restored = RuntimeMessage.from_json(original.to_json(), Mock())
        self.assertEqual(restored.message, "system notice")

    def test_missing_message_crashes(self):
        data = {"role": "user"}
        with self.assertRaises(KeyError):
            RuntimeMessage.from_json(json.dumps(data), Mock())

    def test_extra_fields_ignored(self):
        data = {"role": "user", "message": "hi", "extra": True}
        restored = RuntimeMessage.from_json(json.dumps(data), Mock())
        self.assertEqual(restored.message, "hi")

    def test_inherits_message_protocol(self):
        from linhai.base import Message

        msg = RuntimeMessage("test")
        self.assertIsInstance(msg, Message)

    def test_to_llm_message_format(self):
        msg = RuntimeMessage("notice")
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "user")
        self.assertIn("notice", llm_msg["content"])


class TestDynamicFileContentMessageSerialization(unittest.TestCase):
    def setUp(self):
        self.test_file = Path("test_temp_dyn.txt")
        self.test_file.write_text("line1\nline2")

    def tearDown(self):
        if self.test_file.exists():
            self.test_file.unlink()

    def test_roundtrip_preserves_filepath_and_line_numbers(self):
        original = DynamicFileContentMessage(str(self.test_file), True)
        restored = DynamicFileContentMessage.from_json(original.to_json(), Mock())
        self.assertEqual(restored.filepath, str(self.test_file))
        self.assertTrue(restored.show_line_numbers)

    def test_missing_filepath_crashes(self):
        data = {"show_line_numbers": False}
        with self.assertRaises(KeyError):
            DynamicFileContentMessage.from_json(json.dumps(data), Mock())

    def test_missing_show_line_numbers_crashes(self):
        data = {"filepath": "/tmp/x"}
        with self.assertRaises(KeyError):
            DynamicFileContentMessage.from_json(json.dumps(data), Mock())

    def test_extra_fields_ignored(self):
        data = {"filepath": "/tmp/x", "show_line_numbers": True, "extra": 42}
        restored = DynamicFileContentMessage.from_json(json.dumps(data), Mock())
        self.assertEqual(restored.filepath, "/tmp/x")
        self.assertTrue(restored.show_line_numbers)

    def test_json_does_not_contain_file_content(self):
        msg = DynamicFileContentMessage(str(self.test_file), False)
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertNotIn("content", data)

    def test_restored_reads_latest_content(self):
        original = DynamicFileContentMessage(str(self.test_file), False)
        json_str = original.to_json()
        self.test_file.write_text("new content")
        restored = DynamicFileContentMessage.from_json(json_str, Mock())
        self.assertIn("new content", restored.get_content())

    def test_restored_file_not_found(self):
        msg = DynamicFileContentMessage("/nonexistent/path.txt", False)
        content = msg.get_content()
        self.assertIn("error", content.lower())


class TestPlanningPromptMessage(unittest.TestCase):
    def test_inherits_runtime_message(self):
        msg = PlanningPromptMessage(Path("/tmp/test_planning"))
        self.assertIsInstance(msg, RuntimeMessage)

    def test_file_paths_built_from_planning_folder(self):
        folder = Path("/tmp/my_planning")
        msg = PlanningPromptMessage(folder)
        self.assertEqual(msg.planning_folder, folder)
        self.assertEqual(msg.status_file, folder / "STATUS.md")
        self.assertEqual(msg.todolist_file, folder / "TODOLIST.md")
        self.assertEqual(msg.design_file, folder / "DESIGN.md")

    def test_content_contains_planning_folder_path(self):
        folder = Path("/tmp/test_planning_123")
        msg = PlanningPromptMessage(folder)
        self.assertIn(str(folder / "STATUS.md"), msg.message)
        self.assertIn(str(folder / "TODOLIST.md"), msg.message)
        self.assertIn(str(folder / "DESIGN.md"), msg.message)

    def test_get_file_paths_returns_correct_dict(self):
        folder = Path("/tmp/test_planning")
        msg = PlanningPromptMessage(folder)
        paths = msg.get_file_paths()
        self.assertEqual(paths["status"], folder / "STATUS.md")
        self.assertEqual(paths["todolist"], folder / "TODOLIST.md")
        self.assertEqual(paths["design"], folder / "DESIGN.md")

    def test_serialization_via_runtime_message(self):
        folder = Path("/tmp/test_planning")
        msg = PlanningPromptMessage(folder)
        json_str = msg.to_json()
        restored = RuntimeMessage.from_json(json_str, Mock())
        self.assertEqual(restored.message, msg.message)


def _make_sysmsg_registry():
    from linhai.registry import Registry
    from linhai.tool.main import ToolManager

    registry = Registry()
    mock_tool_manager = Mock(spec=ToolManager)
    mock_tool_manager.get_tools_info = Mock(return_value=[])
    registry.register_member("tool_manager", mock_tool_manager)
    return registry


class TestSystemMessageSerializeRestore(unittest.TestCase):
    def test_serialize_keys(self):
        registry = _make_sysmsg_registry()
        msg = SystemMessage(registry=registry)
        data = msg.serialize()
        self.assertIn("overview", data)
        self.assertIn("introduction_items", data)
        self.assertIn("rules_items", data)
        self.assertIn("examples_items", data)

    def test_roundtrip_with_custom_sections(self):
        registry1 = _make_sysmsg_registry()
        msg = SystemMessage(registry=registry1)
        msg.add_introduction("CUSTOM INTRO", "custom intro content")
        msg.add_rule("CUSTOM RULE", "custom rule content")
        msg.add_example("CUSTOM EXAMPLE", "custom example content")
        data = msg.serialize()

        registry2 = _make_sysmsg_registry()
        msg2 = SystemMessage(registry=registry2)
        msg2.restore_from(data)
        self.assertIn(("CUSTOM INTRO", "custom intro content"), msg2.introduction_items)
        self.assertIn(("CUSTOM RULE", "custom rule content"), msg2.rules_items)
        self.assertIn(("CUSTOM EXAMPLE", "custom example content"), msg2.examples_items)

    def test_restore_missing_overview_crashes(self):
        registry1 = _make_sysmsg_registry()
        msg = SystemMessage(registry=registry1)
        data = msg.serialize()
        del data["overview"]
        registry2 = _make_sysmsg_registry()
        msg2 = SystemMessage(registry=registry2)
        with self.assertRaises(KeyError):
            msg2.restore_from(data)

    def test_to_json_from_json_roundtrip(self):
        registry1 = _make_sysmsg_registry()
        msg = SystemMessage(registry=registry1)
        msg.add_introduction("EXTRA", "extra content")
        json_str = msg.to_json()
        registry2 = _make_sysmsg_registry()
        restored = SystemMessage.from_json(json_str, registry2)
        self.assertIn(["EXTRA", "extra content"], restored.introduction_items)
        self.assertEqual(msg.to_llm_message(), restored.to_llm_message())

    def test_add_invalid_title_crashes(self):
        registry = _make_sysmsg_registry()
        msg = SystemMessage(registry=registry)
        with self.assertRaises(ValueError):
            msg.add_introduction("lowercase", "content")
