import unittest
from unittest.mock import Mock

from linhai.prompt import OVERVIEW, INTRODUCTION_TOOL_USE, RULES_TOOL_USE
from linhai.base import SystemMessage
from linhai.registry import Registry
from linhai.tool.main import ToolManager


class TestSystemMessageStructure(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info = Mock(return_value=[])
        self.registry.register_member("tool_manager", mock_tool_manager)

    def test_content_has_all_sections(self):
        msg = SystemMessage(registry=self.registry)
        content = msg.get_content()
        self.assertIn("# OVERVIEW", content)
        self.assertIn("# INTRODUCTION", content)
        self.assertIn("# RULES", content)
        self.assertIn("# EXAMPLES", content)

    def test_content_includes_constants(self):
        msg = SystemMessage(registry=self.registry)
        content = msg.get_content()
        self.assertIn(OVERVIEW, content)
        self.assertIn(INTRODUCTION_TOOL_USE, content)
        self.assertIn(RULES_TOOL_USE, content)

    def test_to_llm_message_format(self):
        msg = SystemMessage(registry=self.registry)
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "system")
        self.assertIsInstance(llm_msg["content"], str)

    def test_add_introduction(self):
        msg = SystemMessage(registry=self.registry)
        original_len = len(msg.introduction_items)
        msg.add_introduction("CUSTOM", "content")
        self.assertEqual(len(msg.introduction_items), original_len + 1)
        self.assertIn("CUSTOM", msg.get_content())

    def test_remove_introduction(self):
        msg = SystemMessage(registry=self.registry)
        msg.add_introduction("REMOVEME", "content")
        msg.remove_introduction("REMOVEME")
        self.assertNotIn(("REMOVEME", "content"), msg.introduction_items)

    def test_add_and_remove_rule(self):
        msg = SystemMessage(registry=self.registry)
        msg.add_rule("MYRULE", "rule content")
        self.assertIn(("MYRULE", "rule content"), msg.rules_items)
        msg.remove_rule("MYRULE")
        self.assertNotIn(("MYRULE", "rule content"), msg.rules_items)

    def test_add_and_remove_example(self):
        msg = SystemMessage(registry=self.registry)
        msg.add_example("MYEXAMPLE", "example content")
        self.assertIn(("MYEXAMPLE", "example content"), msg.examples_items)
        msg.remove_example("MYEXAMPLE")
        self.assertNotIn(("MYEXAMPLE", "example content"), msg.examples_items)

    def test_invalid_title_crashes(self):
        msg = SystemMessage(registry=self.registry)
        with self.assertRaises(ValueError):
            msg.add_introduction("lowercase", "x")
        with self.assertRaises(ValueError):
            msg.add_rule("WITH!SPECIAL", "x")
        with self.assertRaises(ValueError):
            msg.add_example("中文标题", "x")


def _fresh_registry():
    from linhai.registry import Registry as Reg

    reg = Reg()
    mock_tm = Mock(spec=ToolManager)
    mock_tm.get_tools_info = Mock(return_value=[])
    reg.register_member("tool_manager", mock_tm)
    return reg


class TestSystemMessageSerializeRestore(unittest.TestCase):
    def test_roundtrip_preserves_custom_sections(self):
        msg = SystemMessage(registry=_fresh_registry())
        msg.add_introduction("CUSTOM1", "intro1")
        msg.add_rule("CUSTOM2", "rule2")
        msg.add_example("CUSTOM3", "example3")
        data = msg.serialize()

        restored = SystemMessage(registry=_fresh_registry())
        restored.restore_from(data)
        self.assertIn(("CUSTOM1", "intro1"), restored.introduction_items)
        self.assertIn(("CUSTOM2", "rule2"), restored.rules_items)
        self.assertIn(("CUSTOM3", "example3"), restored.examples_items)

    def test_restore_missing_field_crashes(self):
        msg = SystemMessage(registry=_fresh_registry())
        data = msg.serialize()
        del data["introduction_items"]
        msg2 = SystemMessage(registry=_fresh_registry())
        with self.assertRaises(KeyError):
            msg2.restore_from(data)

    def test_serialize_keys(self):
        msg = SystemMessage(registry=_fresh_registry())
        data = msg.serialize()
        for key in ("overview", "introduction_items", "rules_items", "examples_items"):
            self.assertIn(key, data)

    def test_to_json_from_json(self):
        msg = SystemMessage(registry=_fresh_registry())
        msg.add_introduction("JSON", "json content")
        json_str = msg.to_json()
        restored = SystemMessage.from_json(json_str, _fresh_registry())
        self.assertEqual(msg.get_content(), restored.get_content())
