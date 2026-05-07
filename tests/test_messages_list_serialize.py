import unittest
from unittest import mock

from linhai.parsed_message import (
    NormalSegment,
    ReasoningSegment,
    ToolCallSegment,
)
from linhai.tui.components import (
    UserMessageWidget,
    MessageWidget,
    MessageGenerationWidget,
    RuntimeMessageWidget,
    ToolCallWidget,
    NormalContentWidget,
    ReasoningContentWidget,
)


def _make_user_msg(content: str, sender_name: str = "user") -> mock.MagicMock:
    w = mock.MagicMock(spec=UserMessageWidget)
    w.content_str = content
    w.display_name = sender_name
    return w


def _make_segment_widget(segment: dict) -> mock.MagicMock:
    if segment["segment_type"] == "toolcall":
        w = mock.MagicMock(spec=ToolCallWidget)
    elif segment["segment_type"] == "reasoning":
        w = mock.MagicMock(spec=ReasoningContentWidget)
    else:
        w = mock.MagicMock(spec=NormalContentWidget)
    w._segment = segment
    return w


def _make_message_widget(sender_name: str, segments: list[dict]) -> mock.MagicMock:
    w = mock.MagicMock(spec=MessageWidget)
    w.sender_name = sender_name
    content_mock = mock.MagicMock()
    content_children = []
    for i, seg in enumerate(segments):
        if i > 0:
            spacer = mock.MagicMock()
            content_children.append(spacer)
        content_children.append(_make_segment_widget(seg))
    content_mock.children = content_children
    w._content = content_mock
    return w


def _make_runtime_msg(level: str, content: str) -> mock.MagicMock:
    w = mock.MagicMock(spec=RuntimeMessageWidget)
    w.level = level
    w.content_str = content
    return w


def _make_generation_widget(
    sender_name: str = "deepseek",
    segments: list[dict] | None = None,
    runtime_messages: list[dict] | None = None,
) -> mock.MagicMock:
    children = []
    children.append(_make_message_widget(sender_name, segments or []))
    for rt in runtime_messages or []:
        children.append(_make_runtime_msg(rt["level"], rt["content"]))
    w = mock.MagicMock(spec=MessageGenerationWidget)
    w.children = children
    return w


class TestSerializeUserMessages(unittest.TestCase):
    def test_serialize_user_message(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = [_make_user_msg("hello world", "user")]
        result = ml.serialize()
        self.assertEqual(len(result["messages"]), 1)
        msg = result["messages"][0]
        self.assertEqual(msg["type"], "user")
        self.assertEqual(msg["content"], "hello world")
        self.assertEqual(msg["sender_name"], "user")

    def test_serialize_empty_messages(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = []
        result = ml.serialize()
        self.assertEqual(result, {"messages": []})


class TestSerializeAssistantMessages(unittest.TestCase):
    def test_serialize_normal_segment(self):
        from linhai.tui.messages_list import MessagesList

        segment = NormalSegment(segment_type="normal", content="hi", is_finished=True)
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        self.assertEqual(len(result["messages"]), 1)
        msg = result["messages"][0]
        self.assertEqual(msg["type"], "assistant")
        self.assertEqual(msg["sender_name"], "deepseek")
        self.assertEqual(len(msg["segments"]), 1)
        self.assertEqual(msg["segments"][0]["segment_type"], "normal")
        self.assertEqual(msg["segments"][0]["content"], "hi")
        self.assertTrue(msg["segments"][0]["is_finished"])

    def test_serialize_toolcall_segment(self):
        from linhai.tui.messages_list import MessagesList

        segment = ToolCallSegment(
            segment_type="toolcall",
            raw='{"name": "test"}',
            is_finished=True,
            is_corrupted=False,
            markdown_representation="- name: `test`",
            tool_name="test",
        )
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(msg["segments"][0]["segment_type"], "toolcall")
        self.assertEqual(msg["segments"][0]["tool_name"], "test")
        self.assertFalse(msg["segments"][0]["is_corrupted"])

    def test_serialize_reasoning_segment(self):
        from linhai.tui.messages_list import MessagesList

        segment = ReasoningSegment(
            segment_type="reasoning", content="thinking...", is_finished=True
        )
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(msg["segments"][0]["segment_type"], "reasoning")
        self.assertEqual(msg["segments"][0]["content"], "thinking...")

    def test_serialize_multiple_segments(self):
        from linhai.tui.messages_list import MessagesList

        segments = [
            NormalSegment(segment_type="normal", content="part1", is_finished=True),
            ToolCallSegment(
                segment_type="toolcall",
                raw="{}",
                is_finished=True,
                is_corrupted=False,
                markdown_representation="",
                tool_name="tool1",
            ),
            NormalSegment(segment_type="normal", content="part2", is_finished=True),
        ]
        gen = _make_generation_widget(segments=segments)
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(len(msg["segments"]), 3)

    def test_serialize_with_runtime_messages(self):
        from linhai.tui.messages_list import MessagesList

        segment = NormalSegment(segment_type="normal", content="hi", is_finished=True)
        gen = _make_generation_widget(
            segments=[segment],
            runtime_messages=[{"level": "info", "content": "note"}],
        )
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(len(msg["runtime_messages"]), 1)
        self.assertEqual(msg["runtime_messages"][0]["level"], "info")
        self.assertEqual(msg["runtime_messages"][0]["content"], "note")


class TestSerializeMixedMessages(unittest.TestCase):
    def test_serialize_mixed_user_and_assistant(self):
        from linhai.tui.messages_list import MessagesList

        user_msg = _make_user_msg("hello")
        segment = NormalSegment(
            segment_type="normal", content="hi back", is_finished=True
        )
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [user_msg, gen]
        result = ml.serialize()
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][0]["type"], "user")
        self.assertEqual(result["messages"][1]["type"], "assistant")


class TestRestoreFrom(unittest.TestCase):
    def test_restore_skips_unknown_type(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = []
        ml.pygments_theme = "lightbulb"
        ml.get_refresh_interval = lambda: 0.1
        ml.mount = mock.MagicMock()
        data = {"messages": [{"type": "unknown"}]}
        ml.restore_from(data)
        ml.mount.assert_not_called()
        self.assertEqual(len(ml.messages), 0)

    def test_restore_clears_existing_messages(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = ["old_message"]
        ml.pygments_theme = "lightbulb"
        ml.get_refresh_interval = lambda: 0.1
        ml.mount = mock.MagicMock()
        data = {"messages": []}
        ml.restore_from(data)
        self.assertEqual(ml.messages, [])

    def test_restore_sets_scroll_flag(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = []
        ml.pygments_theme = "lightbulb"
        ml.get_refresh_interval = lambda: 0.1
        ml.mount = mock.MagicMock()
        ml.is_user_scroll_to_end = False
        data = {"messages": []}
        ml.restore_from(data)
        self.assertTrue(ml.is_user_scroll_to_end)


class TestSegmentRoundtrip(unittest.TestCase):
    def test_normal_segment_dict_roundtrip(self):
        original = NormalSegment(
            segment_type="normal", content="test content", is_finished=True
        )
        as_dict = dict(original)
        self.assertEqual(as_dict["segment_type"], "normal")
        self.assertEqual(as_dict["content"], "test content")
        self.assertTrue(as_dict["is_finished"])

    def test_toolcall_segment_dict_roundtrip(self):
        original = ToolCallSegment(
            segment_type="toolcall",
            raw='{"name":"run"}',
            is_finished=True,
            is_corrupted=False,
            markdown_representation="- name: `run`",
            tool_name="run",
        )
        as_dict = dict(original)
        self.assertEqual(as_dict["segment_type"], "toolcall")
        self.assertEqual(as_dict["raw"], '{"name":"run"}')
        self.assertEqual(as_dict["tool_name"], "run")

    def test_reasoning_segment_dict_roundtrip(self):
        original = ReasoningSegment(
            segment_type="reasoning", content="deep thought", is_finished=True
        )
        as_dict = dict(original)
        self.assertEqual(as_dict["segment_type"], "reasoning")
        self.assertEqual(as_dict["content"], "deep thought")
