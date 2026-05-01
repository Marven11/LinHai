import unittest
from unittest.mock import MagicMock, create_autospec, AsyncMock
from tempfile import TemporaryDirectory
from pathlib import Path

from linhai.registry import Registry
from linhai.base import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    MESSAGE_CLASS_REGISTRY,
)
from linhai.agent.message import AgentMessage
from linhai.agent.messages import RuntimeMessage
from linhai.agent.savable_state import SavableState


def _make_registry() -> Registry:
    registry = Registry()
    from linhai.agent.lifecycle import Lifecycle

    Lifecycle(registry)
    from linhai.agent.main import Agent

    mock_agent = create_autospec(Agent, instance=True)
    registry.register_member("agent", mock_agent)
    from linhai.llm_manager import LlmManager

    mock_llm_manager = create_autospec(LlmManager, instance=True)
    mock_llm = MagicMock()
    mock_llm.get_explicit_cache_info = MagicMock(return_value=None)
    mock_llm_manager.get_current_llm = MagicMock(return_value=mock_llm)
    registry.register_member("llm_manager", mock_llm_manager)
    return registry


class TestSystemMessageSerializeRestore(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        self.registry.register_member = MagicMock()

    def test_is_savable_state(self):
        msg = SystemMessage(registry=self.registry)
        self.assertIsInstance(msg, SavableState)

    def test_serialize_roundtrip(self):
        msg = SystemMessage(registry=self.registry)
        msg.add_introduction("CUSTOM INTRO", "custom intro content")
        msg.add_rule("CUSTOM RULE", "custom rule content")
        msg.add_example("CUSTOM EXAMPLE", "custom example content")
        data = msg.serialize()
        msg2 = SystemMessage(registry=self.registry)
        msg2.restore_from(data)
        self.assertEqual(msg.overview, msg2.overview)
        self.assertEqual(msg.introduction_items, msg2.introduction_items)
        self.assertEqual(msg.rules_items, msg2.rules_items)
        self.assertEqual(msg.examples_items, msg2.examples_items)
        self.assertIn(("CUSTOM INTRO", "custom intro content"), msg2.introduction_items)
        self.assertIn(("CUSTOM RULE", "custom rule content"), msg2.rules_items)
        self.assertIn(("CUSTOM EXAMPLE", "custom example content"), msg2.examples_items)

    def test_serialize_keys(self):
        msg = SystemMessage(registry=self.registry)
        data = msg.serialize()
        self.assertIn("overview", data)
        self.assertIn("introduction_items", data)
        self.assertIn("rules_items", data)
        self.assertIn("examples_items", data)


class TestAgentMessageSerializeRestore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = _make_registry()
        self.temp_dir = TemporaryDirectory()
        self.registry.register_member("conversation_folder", Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_agent_message(self, pinned=None, fresh_registry=False):
        if fresh_registry:
            registry = _make_registry()
            registry.register_member("conversation_folder", Path(self.temp_dir.name))
        else:
            registry = self.registry
        return AgentMessage(registry, pinned or [])

    def test_is_savable_state(self):
        am = self._make_agent_message()
        self.assertIsInstance(am, SavableState)

    def test_serialize_empty(self):
        am = self._make_agent_message()
        data = am.serialize()
        self.assertEqual(data["pinned_messages"], [])
        self.assertEqual(data["messages"], [])
        self.assertEqual(data["notification_messages"], [])

    def test_serialize_excludes_system_message(self):
        mock_reg = Registry()
        mock_reg.register_member = MagicMock()
        sys_msg = SystemMessage(registry=mock_reg)
        am = self._make_agent_message(pinned=[sys_msg, RuntimeMessage("hello")])
        data = am.serialize()
        pinned_types = [item["type"] for item in data["pinned_messages"]]
        self.assertNotIn("SystemMessage", pinned_types)
        self.assertIn("RuntimeMessage", pinned_types)

    def test_roundtrip_messages(self):
        am = self._make_agent_message()
        am.messages = [UserMessage("hi"), AssistantMessage("hello")]
        data = am.serialize()
        am2 = self._make_agent_message(fresh_registry=True)
        am2.restore_from(data)
        self.assertEqual(len(am2.messages), 2)
        self.assertIsInstance(am2.messages[0], UserMessage)
        self.assertIsInstance(am2.messages[1], AssistantMessage)
        self.assertEqual(am2.messages[0].message, "hi")
        self.assertEqual(am2.messages[1].message, "hello")

    def test_roundtrip_notification_messages(self):
        am = self._make_agent_message()
        am.update_notification_message(RuntimeMessage("notif"), "test_source", 42)
        data = am.serialize()
        am2 = self._make_agent_message(fresh_registry=True)
        am2.restore_from(data)
        self.assertIn("test_source", am2.notification_messages)
        entry = am2.notification_messages["test_source"]
        self.assertEqual(entry["source"], "test_source")
        self.assertEqual(entry["sort_value"], 42)
        self.assertIsInstance(entry["message"], RuntimeMessage)
        self.assertEqual(entry["message"].message, "notif")

    def test_roundtrip_pinned_excludes_system(self):
        mock_reg = Registry()
        mock_reg.register_member = MagicMock()
        sys_msg = SystemMessage(registry=mock_reg)
        am = self._make_agent_message(pinned=[sys_msg, RuntimeMessage("pinned")])
        am.messages = [UserMessage("user_msg")]
        data = am.serialize()
        am2 = self._make_agent_message(fresh_registry=True)
        am2.restore_from(data)
        self.assertEqual(len(am2.pinned_messages), 1)
        self.assertIsInstance(am2.pinned_messages[0], RuntimeMessage)
        self.assertEqual(am2.pinned_messages[0].message, "pinned")


class TestMessageClassRegistry(unittest.TestCase):
    def test_registry_contains_key_types(self):
        for name in [
            "RuntimeMessage",
            "UserMessage",
            "AssistantMessage",
            "DynamicFileContentMessage",
            "ExplicitCacheMessage",
        ]:
            self.assertIn(name, MESSAGE_CLASS_REGISTRY)

    def test_registry_has_from_json(self):
        for name, cls in MESSAGE_CLASS_REGISTRY.items():
            self.assertTrue(hasattr(cls, "from_json"), f"{name} missing from_json")


if __name__ == "__main__":
    unittest.main()
