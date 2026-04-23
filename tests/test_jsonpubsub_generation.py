from __future__ import annotations

import unittest

from linhai.utils.jsonpubsub import JsonPublisher, JsonSubscriber


class TestGenerationCounter(unittest.TestCase):
    def test_generation_increments_on_reset(self):
        data = {"key": "value"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()

        data["key"] = "v1"
        for e in pub.calculate_diff():
            sub.update_data(e)
        self.assertEqual(sub.data, {"key": "v1"})

        reset_event = pub.reset()
        self.assertEqual(reset_event["gen"], 1)
        sub.update_data(reset_event)

        data["key"] = "v2"
        for e in pub.calculate_diff():
            sub.update_data(e)
        self.assertEqual(sub.data, {"key": "v2"})

    def test_stale_events_skipped_after_reset(self):
        data = {"key": "value"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()

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

    def test_multiple_resets(self):
        data = {"msg": "hello"}
        pub = JsonPublisher(data)
        sub = JsonSubscriber()

        data["msg"] = "world"
        for e in pub.calculate_diff():
            sub.update_data(e)

        reset1 = pub.reset()
        sub.update_data(reset1)
        self.assertEqual(reset1["gen"], 1)

        data["msg"] = "reset1"
        for e in pub.calculate_diff():
            sub.update_data(e)

        reset2 = pub.reset()
        sub.update_data(reset2)
        self.assertEqual(reset2["gen"], 2)

        data["msg"] = "reset2"
        for e in pub.calculate_diff():
            sub.update_data(e)

        self.assertEqual(sub.data, {"msg": "reset2"})

    def test_desynced_subscriber_recovers(self):
        data = {"messages": [], "status_bar": []}
        pub = JsonPublisher(data)
        synced_sub = JsonSubscriber()

        data["messages"].append({"type": "user", "content": "hi"})
        for e in pub.calculate_diff():
            synced_sub.update_data(e)

        reset_event = pub.reset()
        synced_sub.update_data(reset_event)

        desynced_sub = JsonSubscriber()
        desynced_sub.update_data(reset_event)

        data["status_bar"].append("test")
        new_events = pub.calculate_diff()

        for e in new_events:
            synced_sub.update_data(e)
            desynced_sub.update_data(e)

        self.assertEqual(synced_sub.data, desynced_sub.data)

    def test_backward_compat_events_without_gen(self):
        data = {"key": "value"}
        sub = JsonSubscriber()

        event_no_gen = {
            "idx": -1,
            "event": {"action": "replace", "keys": [], "value": {"key": "val"}},
        }
        sub.update_data(event_no_gen)
        self.assertEqual(sub.data, {"key": "val"})


if __name__ == "__main__":
    unittest.main()
