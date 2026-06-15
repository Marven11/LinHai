import asyncio
import copy
import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.utils.jsonpubsub import JsonPublisher, JsonSubscriber, TaggedEvent
from linhai.webui.schemas import (
    WebuiSegmentType,
)
from linhai.webui.agent_manager import AgentSession


def apply_reset_to_subscriber(sub: JsonSubscriber, reset_event: TaggedEvent):
    sub.data = copy.deepcopy(reset_event["event"]["value"])
    sub.event_counter = 0
    sub._generation = reset_event.get("gen", 0)


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
        msgs = session._data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[0]["content"], "hello")

    async def test_add_notification(self):
        session = self._make_session()
        session.add_notification("INFO", "test notice")
        msgs = session._data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "notification")
        self.assertEqual(msgs[0]["level"], "INFO")

    async def test_add_agent_message(self):
        session = self._make_session()
        idx = session.add_agent_message()
        self.assertEqual(idx, 0)
        msgs = session._data["messages"]
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
        agent_msg = session._data["messages"][idx]
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
        agent_msg = session._data["messages"][idx]
        self.assertEqual(agent_msg["segments"][0]["content"], "hello world")
        self.assertTrue(agent_msg["segments"][0]["is_finished"])

    async def test_update_agent_message_content(self):
        session = self._make_session()
        idx = session.add_agent_message()
        session.update_agent_message_content(idx, "full response")
        agent_msg = session._data["messages"][idx]
        self.assertEqual(agent_msg["content"], "full response")

    async def test_multiple_messages_order(self):
        session = self._make_session()
        session.add_user_message("hi")
        idx = session.add_agent_message()
        session.update_agent_message_content(idx, "hello")
        session.add_notification("INFO", "done")
        msgs = session._data["messages"]
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[1]["type"], "agent")
        self.assertEqual(msgs[2]["type"], "notification")

    async def test_add_empty_user_message(self):
        session = self._make_session()
        session.add_user_message("")
        msgs = session._data["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "user")
        self.assertEqual(msgs[0]["content"], "")

    async def test_multiple_segments_in_one_agent_message(self):
        session = self._make_session()
        idx = session.add_agent_message()
        seg1: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "hello",
            "is_finished": True,
        }
        seg2: WebuiSegmentType = {
            "segment_type": "normal",
            "content": " world",
            "is_finished": False,
        }
        session.add_segment_to_agent_message(idx, seg1)
        session.add_segment_to_agent_message(idx, seg2)
        agent_msg = session._data["messages"][idx]
        self.assertEqual(len(agent_msg["segments"]), 2)
        self.assertEqual(agent_msg["segments"][0]["content"], "hello")
        self.assertTrue(agent_msg["segments"][0]["is_finished"])
        self.assertEqual(agent_msg["segments"][1]["content"], " world")
        self.assertFalse(agent_msg["segments"][1]["is_finished"])

    async def test_segment_completion_state_transition(self):
        session = self._make_session()
        idx = session.add_agent_message()
        seg: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "partial",
            "is_finished": False,
        }
        session.add_segment_to_agent_message(idx, seg)
        self.assertFalse(session._data["messages"][idx]["segments"][0]["is_finished"])
        seg["content"] = "complete"
        seg["is_finished"] = True
        self.assertTrue(session._data["messages"][idx]["segments"][0]["is_finished"])
        self.assertEqual(
            session._data["messages"][idx]["segments"][0]["content"], "complete"
        )

    async def test_two_sessions_independent_messages(self):
        s1 = self._make_session()
        s2 = self._make_session()
        s1.add_user_message("msg-from-s1")
        s2.add_user_message("msg-from-s2")
        self.assertEqual(len(s1._data["messages"]), 1)
        self.assertEqual(s1._data["messages"][0]["content"], "msg-from-s1")
        self.assertEqual(len(s2._data["messages"]), 1)
        self.assertEqual(s2._data["messages"][0]["content"], "msg-from-s2")


class TestJsonPubSubWithMessages(unittest.TestCase):
    def _init_pub_sub(self):
        data = {"messages": []}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        for e in pub.calculate_diff():
            sub.update_data(e)
        return data, pub, sub

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

    def test_reset_then_continue_diff(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        reset_event = pub.reset()

        sub2 = JsonSubscriber()
        sub2.update_data(reset_event)

        data["messages"].append({"type": "user", "content": "world"})
        for e in pub.calculate_diff():
            sub2.update_data(e)

        self.assertEqual(len(sub2.data["messages"]), 2)
        self.assertEqual(sub2.data["messages"][1]["content"], "world")

    def test_reset_preserves_existing_state(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "alpha"})
        data["messages"].append({"type": "user", "content": "beta"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        reset_event = pub.reset()
        new_sub = JsonSubscriber()
        apply_reset_to_subscriber(new_sub, reset_event)

        self.assertEqual(len(new_sub.data["messages"]), 2)
        self.assertEqual(new_sub.data["messages"][0]["content"], "alpha")
        self.assertEqual(new_sub.data["messages"][1]["content"], "beta")

    def test_reset_then_multiple_diffs_consistent(self):
        data, pub, _ = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "first"})
        reset_event = pub.reset()

        sub = JsonSubscriber()
        sub.update_data(reset_event)

        data["messages"].append({"type": "user", "content": "second"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        data["messages"].append(
            {"type": "notification", "level": "WARN", "content": "alert"}
        )
        for e in pub.calculate_diff():
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 3)
        self.assertEqual(sub.data["messages"][0]["content"], "first")
        self.assertEqual(sub.data["messages"][1]["content"], "second")
        self.assertEqual(sub.data["messages"][2]["type"], "notification")

    def test_no_diff_when_no_changes(self):
        data, pub, sub = self._init_pub_sub()

        data["messages"].append({"type": "user", "content": "hello"})
        for e in pub.calculate_diff():
            sub.update_data(e)

        events = pub.calculate_diff()
        self.assertEqual(len(events), 0)

    def test_subscriber_initial_state(self):
        sub = JsonSubscriber()
        self.assertIsNone(sub.data)
        self.assertEqual(sub.event_counter, 0)


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
        self.assertEqual(
            events[0]["event"]["value"],
            {
                "messages": [],
                "processes": [],
                "status_bar": [],
                "context": {},
                "planning": {},
            },
        )

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

    async def test_diff_after_reset_then_add(self):
        session = self._make_session()

        session.add_user_message("hello")
        await session.get_diff()

        reset_event = await session.handle_reset()

        sub = JsonSubscriber()
        sub.update_data(reset_event)

        session.add_user_message("world")
        events = await session.get_diff()
        for e in events:
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 2)
        self.assertEqual(sub.data["messages"][1]["content"], "world")

    async def test_reset_preserves_existing_messages(self):
        session = self._make_session()
        sub = JsonSubscriber()
        for e in await session.get_diff():
            sub.update_data(e)

        session.add_user_message("alpha")
        session.add_user_message("beta")
        for e in await session.get_diff():
            sub.update_data(e)

        reset_event = await session.handle_reset()
        new_sub = JsonSubscriber()
        apply_reset_to_subscriber(new_sub, reset_event)

        self.assertEqual(len(new_sub.data["messages"]), 2)
        self.assertEqual(new_sub.data["messages"][0]["content"], "alpha")
        self.assertEqual(new_sub.data["messages"][1]["content"], "beta")

    async def test_two_sessions_have_independent_diffs(self):
        s1 = self._make_session()
        s2 = self._make_session()

        s1.add_user_message("from-s1")
        s2.add_user_message("from-s2")

        e1 = await s1.get_diff()
        e2 = await s2.get_diff()

        s1_sub = JsonSubscriber()
        for e in e1:
            s1_sub.update_data(e)
        s2_sub = JsonSubscriber()
        for e in e2:
            s2_sub.update_data(e)

        self.assertEqual(s1_sub.data["messages"][0]["content"], "from-s1")
        self.assertEqual(s2_sub.data["messages"][0]["content"], "from-s2")

    async def test_mid_conversation_reset_then_continue(self):
        session = self._make_session()

        session.add_user_message("q1")
        session.add_user_message("q2")
        await session.get_diff()

        reset_event = await session.handle_reset()
        sub = JsonSubscriber()
        sub.update_data(reset_event)

        session.add_user_message("q3")
        seg: WebuiSegmentType = {
            "segment_type": "normal",
            "content": "streaming",
            "is_finished": False,
        }
        idx = session.add_agent_message()
        session.add_segment_to_agent_message(idx, seg)

        events = await session.get_diff()
        for e in events:
            sub.update_data(e)

        self.assertEqual(len(sub.data["messages"]), 4)
        self.assertEqual(sub.data["messages"][0]["content"], "q1")
        self.assertEqual(sub.data["messages"][2]["content"], "q3")
        self.assertEqual(sub.data["messages"][3]["type"], "agent")


if __name__ == "__main__":
    unittest.main()
