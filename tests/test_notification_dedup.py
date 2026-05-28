import unittest
from unittest.mock import MagicMock, create_autospec

from linhai.registry import Registry
from linhai.agent.message import AgentMessage
from linhai.agent.messages import RuntimeMessage


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


def _raw(msg):
    return msg.get_content().replace("<<runtime>>", "").replace("<</runtime>>", "")


class TestNotificationMessageDedup(unittest.TestCase):
    def setUp(self):
        self.registry = _make_registry()

    def test_new_message_added_to_messages(self):
        am = AgentMessage(self.registry, [])
        msg = RuntimeMessage("hello")
        am.update_notification_message(msg, "test_source")
        self.assertIn(msg, am.messages)

    def test_same_message_not_added_twice(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("hello"), "test_source")
        am.update_notification_message(RuntimeMessage("hello"), "test_source")
        count = sum(1 for m in am.messages if _raw(m) == "hello")
        self.assertEqual(count, 1)

    def test_different_message_added(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("first"), "test_source")
        am.update_notification_message(RuntimeMessage("second"), "test_source")
        contents = [_raw(m) for m in am.messages]
        self.assertEqual(contents, ["first", "second"])

    def test_none_clears_tracking(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("hello"), "test_source")
        am.update_notification_message(None, "test_source")
        self.assertIsNone(am.notification_messages["test_source"])

    def test_none_then_same_readds(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("hello"), "test_source")
        am.update_notification_message(None, "test_source")
        am.update_notification_message(RuntimeMessage("hello"), "test_source")
        count = sum(1 for m in am.messages if _raw(m) == "hello")
        self.assertEqual(count, 2)

    def test_different_sources_independent(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("a"), "source_a")
        am.update_notification_message(RuntimeMessage("a"), "source_b")
        self.assertEqual(len(am.messages), 2)

    def test_get_messages_no_duplicate_notifications(self):
        am = AgentMessage(self.registry, [])
        am.update_notification_message(RuntimeMessage("notif"), "src")
        am.update_notification_message(RuntimeMessage("notif"), "src")
        msgs = am.get_messages()
        notif_count = sum(1 for m in msgs if _raw(m) == "notif")
        self.assertEqual(notif_count, 1)


if __name__ == "__main__":
    unittest.main()
