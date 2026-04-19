import asyncio
import copy
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.jsonpubsub import JsonPublisher, JsonSubscriber, TaggedEvent
from linhai.webui.schemas import (
    WebuiUserMessage,
    WebuiNotificationMessage,
    WebuiAgentMessage,
    WebuiSegmentType,
)
from linhai.webui.agent_manager import AgentSession


def apply_reset_to_subscriber(sub: JsonSubscriber, reset_event: TaggedEvent):
    sub.data = copy.deepcopy(reset_event["event"]["value"])
    sub.event_counter = 0


class TestWebuiMessageTypes(unittest.TestCase):
    def test_user_message(self):
        msg: WebuiUserMessage = {"type": "user", "content": "hello"}
        self.assertEqual(msg["type"], "user")
        self.assertEqual(msg["content"], "hello")

    def test_notification_message(self):
        msg: WebuiNotificationMessage = {
            "type": "notification",
            "level": "INFO",
            "content": "test notice",
        }
        self.assertEqual(msg["type"], "notification")
        self.assertEqual(msg["level"], "INFO")

    def test_agent_message(self):
        msg: WebuiAgentMessage = {
            "type": "agent",
            "content": "",
            "segments": [],
        }
        self.assertEqual(msg["type"], "agent")
        self.assertEqual(msg["segments"], [])

    def test_segment_type(self):
        seg: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "hello",
            "is_finished": False,
        }
        self.assertEqual(seg["segment_type"], "normal")
        self.assertFalse(seg["is_finished"])


class TestAgentSessionMessages(unittest.IsolatedAsyncioTestCase):
    def _make_session(self):
        mock_agent = MagicMock()
        mock_agent.state_machine.state = "waiting_user"
        mock_registry = MagicMock()
        mock_registry.send = AsyncMock()
        mock_agent.registry = mock_registry
        mock_manager = MagicMock()
        return AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )

    async def test_add_user_message(self):
        session = self._make_session()
        session.add_user_message("hello")
        msgs = session._messages_data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[0]["content"], "hello")

    async def test_add_notification(self):
        session = self._make_session()
        session.add_notification("INFO", "test notice")
        msgs = session._messages_data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "notification")
        self.assertEqual(msgs[0]["level"], "INFO")

    async def test_add_agent_message(self):
        session = self._make_session()
        idx = session.add_agent_message()
        self.assertEqual(idx, 0)
        msgs = session._messages_data["messages"]
        self.assertEqual(msgs[0]["type"], "agent")
        self.assertEqual(msgs[0]["content"], "")
        self.assertEqual(msgs[0]["segments"], [])

    async def test_add_segment_to_agent_message(self):
        session = self._make_session()
        idx = session.add_agent_message()
        seg: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "hello",
            "is_finished": False,
        }
        session.add_segment_to_agent_message(idx, seg)
        agent_msg = session._messages_data["messages"][idx]
        self.assertEqual(len(agent_msg["segments"]), 1)
        self.assertEqual(agent_msg["segments"][0]["content"], "hello")

    async def test_segment_mutation_reflects_in_agent_message(self):
        session = self._make_session()
        idx = session.add_agent_message()
        seg: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "hello",
            "is_finished": False,
        }
        session.add_segment_to_agent_message(idx, seg)
        seg["content"] += " world"
        seg["is_finished"] = True
        agent_msg = session._messages_data["messages"][idx]
        self.assertEqual(agent_msg["segments"][0]["content"], "hello world")
        self.assertTrue(agent_msg["segments"][0]["is_finished"])

    async def test_update_agent_message_content(self):
        session = self._make_session()
        idx = session.add_agent_message()
        session.update_agent_message_content(idx, "full response")
        agent_msg = session._messages_data["messages"][idx]
        self.assertEqual(agent_msg["content"], "full response")

    async def test_multiple_messages_order(self):
        session = self._make_session()
        session.add_user_message("hi")
        idx = session.add_agent_message()
        session.update_agent_message_content(idx, "hello")
        session.add_notification("INFO", "done")
        msgs = session._messages_data["messages"]
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[1]["type"], "agent")
        self.assertEqual(msgs[2]["type"], "notification")


class TestJsonPubSubWithMessages(unittest.TestCase):
    def _init_pub_sub(self):
        data = {"messages": []}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        for e in pub.calculate_diff():
            sub.update_data(e)
        return data, pub, sub

    def test_diff_after_add_user_message(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)
        self.assertEqual(sub.data, {"messages": [{"type": "user", "content": "hello"}]})

    def test_diff_after_add_agent_message_with_segment(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "agent", "content": "", "segments": []})
        for e in pub.calculate_diff():
            sub.update_data(e)

        seg = {"segment_type": "normal", "content": "hi", "is_finished": False}
        data["messages"][0]["segments"].append(seg)
        for e in pub.calculate_diff():
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"][0]["segments"]), 1)
        self.assertEqual(sub.data["messages"][0]["segments"][0]["content"], "hi")

    def test_diff_after_segment_content_update(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "agent", "content": "", "segments": []})
        for e in pub.calculate_diff():
            sub.update_data(e)

        seg = {"segment_type": "normal", "content": "hi", "is_finished": False}
        data["messages"][0]["segments"].append(seg)
        for e in pub.calculate_diff():
            sub.update_data(e)

        seg["content"] += " world"
        for e in pub.calculate_diff():
            sub.update_data(e)

        self.assertEqual(sub.data["messages"][0]["segments"][0]["content"], "hi world")

    def test_full_conversation_flow(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        data["messages"].append({"type": "agent", "content": "", "segments": []})
        agent_idx = len(data["messages"]) - 1
        for e in pub.calculate_diff():
            sub.update_data(e)

        seg = {"segment_type": "normal", "content": "hi", "is_finished": False}
        data["messages"][agent_idx]["segments"].append(seg)
        for e in pub.calculate_diff():
            sub.update_data(e)

        seg["content"] += " there"
        seg["is_finished"] = True
        for e in pub.calculate_diff():
            sub.update_data(e)

        data["messages"][agent_idx]["content"] = "hi there"
        for e in pub.calculate_diff():
            sub.update_data(e)

        data["messages"].append(
            {"type": "notification", "level": "INFO", "content": "done"}
        )
        for e in pub.calculate_diff():
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 3)
        self.assertEqual(sub.data["messages"][0]["type"], "user")
        self.assertEqual(sub.data["messages"][0]["content"], "hello")
        self.assertEqual(sub.data["messages"][1]["type"], "agent")
        self.assertEqual(sub.data["messages"][1]["content"], "hi there")
        self.assertEqual(sub.data["messages"][1]["segments"][0]["content"], "hi there")
        self.assertTrue(sub.data["messages"][1]["segments"][0]["is_finished"])
        self.assertEqual(sub.data["messages"][2]["type"], "notification")

    def test_reset_rebuilds_subscriber(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        data["messages"].append({"type": "agent", "content": "hi", "segments": []})
        for e in pub.calculate_diff():
            sub.update_data(e)

        reset_event = pub.reset()
        self.assertEqual(reset_event["idx"], -1)
        self.assertEqual(reset_event["event"]["action"], "replace")

        new_sub = JsonSubscriber()
        apply_reset_to_subscriber(new_sub, reset_event)
        self.assertEqual(len(new_sub.data["messages"]), 2)
        self.assertEqual(new_sub.data["messages"][0]["content"], "hello")

    def test_reset_then_continue_diff(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        pub.reset()

        sub2 = JsonSubscriber()
        sub2.data = copy.deepcopy(data)
        sub2.event_counter = 0

        data["messages"].append({"type": "user", "content": "world"})
        for e in pub.calculate_diff():
            sub2.update_data(e)

        self.assertEqual(len(sub2.data["messages"]), 2)
        self.assertEqual(sub2.data["messages"][1]["content"], "world")


class TestAgentSessionPubSubIntegration(unittest.IsolatedAsyncioTestCase):
    def _make_session(self):
        mock_agent = MagicMock()
        mock_agent.state_machine.state = "waiting_user"
        mock_registry = MagicMock()
        mock_registry.send = AsyncMock()
        mock_agent.registry = mock_registry
        mock_manager = MagicMock()
        return AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )

    async def test_first_diff_is_initial_state(self):
        session = self._make_session()
        events = await session.get_diff()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"]["action"], "replace")
        self.assertEqual(events[0]["event"]["value"], {"messages": []})

    async def test_diff_after_add_returns_events(self):
        session = self._make_session()
        await session.get_diff()

        session.add_user_message("hello")
        events = await session.get_diff()
        self.assertTrue(len(events) > 0)

    async def test_diff_after_multiple_changes(self):
        session = self._make_session()
        sub = JsonSubscriber()
        for e in await session.get_diff():
            sub.update_data(e)

        session.add_user_message("hello")
        idx = session.add_agent_message()
        session.update_agent_message_content(idx, "response")

        events = await session.get_diff()
        for e in events:
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 2)
        self.assertEqual(sub.data["messages"][0]["type"], "user")
        self.assertEqual(sub.data["messages"][1]["type"], "agent")
        self.assertEqual(sub.data["messages"][1]["content"], "response")

    async def test_handle_reset(self):
        session = self._make_session()
        sub = JsonSubscriber()
        for e in await session.get_diff():
            sub.update_data(e)

        session.add_user_message("hello")
        for e in await session.get_diff():
            sub.update_data(e)

        reset_event = await session.handle_reset()
        self.assertEqual(reset_event["idx"], -1)

        apply_reset_to_subscriber(sub, reset_event)
        self.assertEqual(len(sub.data["messages"]), 1)
        self.assertEqual(sub.data["messages"][0]["content"], "hello")

    async def test_diff_after_reset_then_add(self):
        session = self._make_session()

        session.add_user_message("hello")
        await session.get_diff()

        await session.handle_reset()

        sub = JsonSubscriber()
        sub.data = copy.deepcopy(session._messages_data)

        session.add_user_message("world")
        events = await session.get_diff()
        for e in events:
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 2)
        self.assertEqual(sub.data["messages"][1]["content"], "world")


class TestAgentSessionSend(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_adds_to_messages(self):
        mock_agent = MagicMock()
        mock_agent.state_machine.state = "waiting_user"
        mock_registry = MagicMock()
        mock_registry.send = AsyncMock()
        mock_agent.registry = mock_registry
        mock_manager = MagicMock()
        session = AgentSession(
            agent_id="test-id",
            agent=mock_agent,
            task_name="task-1",
            manager=mock_manager,
        )
        await session.send_message("hello")
        mock_registry.send.assert_called_once()
        msgs = session._messages_data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[0]["content"], "hello")
