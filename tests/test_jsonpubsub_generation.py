from __future__ import annotations

import copy
import unittest

from linhai.utils.jsonpubsub import (
    JsonPublisher,
    JsonSubscriber,
    calculate_diff,
)


def _apply_all(pub: JsonPublisher, sub: JsonSubscriber):
    for event in pub.calculate_diff():
        sub.update_data(event)


class TestCalculateDiffActions(unittest.TestCase):
    def test_scalar_replace(self):
        events = calculate_diff(1, 2)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")
        self.assertEqual(events[0]["value"], 2)

    def test_no_change_no_events(self):
        self.assertEqual(calculate_diff("same", "same"), [])
        self.assertEqual(calculate_diff(42, 42), [])
        self.assertEqual(calculate_diff({"a": 1}, {"a": 1}), [])
        self.assertEqual(calculate_diff([1, 2], [1, 2]), [])

    def test_string_concat(self):
        events = calculate_diff("hello", "hello world")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "concat")
        self.assertEqual(events[0]["value"], " world")

    def test_string_replace_when_not_prefix(self):
        events = calculate_diff("abc", "xyz")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")

    def test_dict_value_replace(self):
        events = calculate_diff({"a": 1, "b": 2}, {"a": 1, "b": 3})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")
        self.assertEqual(events[0]["keys"], ["b"])
        self.assertEqual(events[0]["value"], 3)

    def test_dict_key_set_change_replaces_all(self):
        events = calculate_diff({"a": 1}, {"b": 2})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")
        self.assertEqual(events[0]["keys"], [])

    def test_dict_multi_value_replace(self):
        old = {"a": 1, "b": 2}
        new = {"a": 10, "b": 20}
        events = calculate_diff(old, new)
        self.assertEqual(len(events), 2)

    def test_list_element_replace(self):
        events = calculate_diff([1, 2, 3], [1, 5, 3])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")
        self.assertEqual(events[0]["keys"], [1])

    def test_list_append(self):
        events = calculate_diff([1, 2], [1, 2, 3])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "insert")

    def test_type_change_replaces_all(self):
        events = calculate_diff({"a": 1}, [1, 2])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "replace")
        self.assertEqual(events[0]["value"], [1, 2])

    def test_nested_dict_replace(self):
        old = {"config": {"port": 8080, "host": "localhost"}}
        new = {"config": {"port": 9090, "host": "localhost"}}
        events = calculate_diff(old, new)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["keys"], ["config", "port"])
        self.assertEqual(events[0]["value"], 9090)


class TestPublisherSubscriberStateMachine(unittest.TestCase):
    def setUp(self):
        self.data = {"messages": [], "status": "idle"}
        self.pub = JsonPublisher(self.data)
        self.sub = JsonSubscriber()

    def test_initial_replace(self):
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data, {"messages": [], "status": "idle"})

    def test_scalar_replace_sequence(self):
        _apply_all(self.pub, self.sub)

        self.data["status"] = "working"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["status"], "working")

        self.data["status"] = "done"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["status"], "done")

    def test_list_insert_sequence(self):
        _apply_all(self.pub, self.sub)

        self.data["messages"].append({"type": "user", "content": "hello"})
        _apply_all(self.pub, self.sub)
        self.assertEqual(len(self.sub.data["messages"]), 1)

        self.data["messages"].append({"type": "assistant", "content": "hi"})
        _apply_all(self.pub, self.sub)
        self.assertEqual(len(self.sub.data["messages"]), 2)
        self.assertEqual(self.sub.data["messages"][1]["type"], "assistant")

    def test_nested_list_replace(self):
        _apply_all(self.pub, self.sub)

        self.data["messages"] = [{"type": "user", "content": "msg1"}]
        _apply_all(self.pub, self.sub)

        self.data["messages"][0]["content"] = "updated"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["messages"][0]["content"], "updated")

    def test_concat_accumulates(self):
        self.data = {"text": ""}
        self.pub = JsonPublisher(self.data)
        self.sub = JsonSubscriber()
        _apply_all(self.pub, self.sub)

        self.data["text"] = "hello"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["text"], "hello")

        self.data["text"] += " world"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["text"], "hello world")

        self.data["text"] += "!"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data["text"], "hello world!")

    def test_multiple_keys_simultaneous_change(self):
        self.data = {"a": 0, "b": 0, "c": 0}
        self.pub = JsonPublisher(self.data)
        self.sub = JsonSubscriber()
        _apply_all(self.pub, self.sub)

        self.data["a"] = 1
        self.data["b"] = 2
        self.data["c"] = 3
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data, {"a": 1, "b": 2, "c": 3})

    def test_subscriber_final_state_matches_publisher(self):
        _apply_all(self.pub, self.sub)
        for i in range(10):
            self.data["messages"].append({"idx": i})
            _apply_all(self.pub, self.sub)
        self.data["status"] = "complete"
        _apply_all(self.pub, self.sub)
        self.assertEqual(self.sub.data, copy.deepcopy(self.data))

    def test_out_of_order_event_raises(self):
        _apply_all(self.pub, self.sub)
        self.data["status"] = "x"
        events = self.pub.calculate_diff()
        self.assertGreater(len(events), 0)
        bad_event = dict(events[0])
        bad_event["idx"] = self.sub.event_counter + 999
        with self.assertRaises(RuntimeError):
            self.sub.update_data(bad_event)


class TestGenerationIsolation(unittest.TestCase):
    def test_reset_increments_generation(self):
        data = {"key": "value"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        _apply_all(pub, sub)

        reset_event = pub.reset()
        self.assertEqual(reset_event["gen"], 1)
        self.assertEqual(reset_event["idx"], -1)
        sub.update_data(reset_event)

        data["key"] = "new_value"
        _apply_all(pub, sub)
        self.assertEqual(sub.data, {"key": "new_value"})

    def test_stale_events_from_old_generation_ignored(self):
        data = {"key": "v0"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        _apply_all(pub, sub)

        data["key"] = "v1"
        stale_events = pub.calculate_diff()

        reset_event = pub.reset()
        sub.update_data(reset_event)

        data["key"] = "v2"
        new_events = pub.calculate_diff()

        for e in stale_events:
            sub.update_data(e)
        for e in new_events:
            sub.update_data(e)
        self.assertEqual(sub.data, {"key": "v2"})

    def test_multiple_resets_generation_counter(self):
        data = {"msg": "init"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        _apply_all(pub, sub)

        for i in range(5):
            data["msg"] = f"reset_{i}"
            _apply_all(pub, sub)
            reset_event = pub.reset()
            self.assertEqual(reset_event["gen"], i + 1)
            sub.update_data(reset_event)

        self.assertEqual(sub.data["msg"], "reset_4")

    def test_desynced_subscriber_recovers_via_reset(self):
        data = {"messages": [], "status_bar": []}
        pub = JsonPublisher(data)
        synced_sub = JsonSubscriber()
        _apply_all(pub, synced_sub)

        data["messages"].append({"type": "user", "content": "hi"})
        _apply_all(pub, synced_sub)

        reset_event = pub.reset()
        synced_sub.update_data(reset_event)

        fresh_sub = JsonSubscriber()
        fresh_sub.update_data(reset_event)

        data["status_bar"].append("online")
        _apply_all(pub, synced_sub)
        _apply_all(pub, fresh_sub)

        self.assertEqual(synced_sub.data, fresh_sub.data)

    def test_backward_compat_event_without_gen(self):
        sub = JsonSubscriber()
        event_no_gen = {
            "idx": -1,
            "event": {"action": "replace", "keys": [], "value": {"key": "val"}},
        }
        sub.update_data(event_no_gen)
        self.assertEqual(sub.data, {"key": "val"})


class TestEventCounterConsistency(unittest.TestCase):
    def test_counter_increments_per_event(self):
        data = {"a": 0, "b": 0}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        _apply_all(pub, sub)

        data["a"] = 1
        data["b"] = 2
        events = pub.calculate_diff()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["idx"], sub.event_counter)
        self.assertEqual(events[1]["idx"], sub.event_counter + 1)

        for e in events:
            sub.update_data(e)
        self.assertEqual(sub.event_counter, pub.event_counter)

    def test_counter_reset_on_generation_change(self):
        data = {"key": "value"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()
        _apply_all(pub, sub)

        self.assertGreater(pub.event_counter, 0)

        reset_event = pub.reset()
        sub.update_data(reset_event)
        self.assertEqual(sub.event_counter, 0)
        self.assertEqual(pub.event_counter, 0)
