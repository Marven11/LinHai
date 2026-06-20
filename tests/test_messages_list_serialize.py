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


class TestSerializeComplexAssistantMessages(unittest.TestCase):
    def test_mixed_segments_assistant_message(self):
        from linhai.tui.messages_list import MessagesList

        segments = [
            NormalSegment(
                segment_type="normal", content="Let me check", is_finished=True
            ),
            ToolCallSegment(
                segment_type="toolcall",
                raw='{"name": "read_file", "arguments": {"path": "/etc"}}',
                is_finished=True,
                is_corrupted=False,
                markdown_representation="- name: `read_file`",
                tool_name="read_file",
            ),
            NormalSegment(
                segment_type="normal", content="The file says:", is_finished=True
            ),
            ReasoningSegment(
                segment_type="reasoning", content="analyzing...", is_finished=True
            ),
        ]
        gen = _make_generation_widget(segments=segments)
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(msg["type"], "assistant")
        self.assertEqual(len(msg["segments"]), 4)
        self.assertEqual(msg["segments"][0]["segment_type"], "normal")
        self.assertEqual(msg["segments"][1]["segment_type"], "toolcall")
        self.assertEqual(msg["segments"][1]["tool_name"], "read_file")
        self.assertEqual(msg["segments"][2]["segment_type"], "normal")
        self.assertEqual(msg["segments"][3]["segment_type"], "reasoning")

    def test_corrupted_toolcall_segment(self):
        from linhai.tui.messages_list import MessagesList

        segment = ToolCallSegment(
            segment_type="toolcall",
            raw='{"invalid',
            is_finished=True,
            is_corrupted=True,
            markdown_representation="<bad toolcall>",
            tool_name="",
        )
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        seg = msg["segments"][0]
        self.assertTrue(seg["is_corrupted"])
        self.assertEqual(seg["segment_type"], "toolcall")

    def test_unfinished_segment(self):
        from linhai.tui.messages_list import MessagesList

        segment = NormalSegment(
            segment_type="normal", content="partial...", is_finished=False
        )
        gen = _make_generation_widget(segments=[segment])
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        self.assertFalse(result["messages"][0]["segments"][0]["is_finished"])

    def test_assistant_with_runtime_messages(self):
        from linhai.tui.messages_list import MessagesList

        segment = NormalSegment(segment_type="normal", content="hi", is_finished=True)
        gen = _make_generation_widget(
            segments=[segment],
            runtime_messages=[
                {"level": "info", "content": "notice1"},
                {"level": "warning", "content": "notice2"},
            ],
        )
        ml = object.__new__(MessagesList)
        ml.messages = [gen]
        result = ml.serialize()
        msg = result["messages"][0]
        self.assertEqual(len(msg["runtime_messages"]), 2)
        self.assertEqual(msg["runtime_messages"][0]["level"], "info")
        self.assertEqual(msg["runtime_messages"][1]["content"], "notice2")


class TestSerializeMixedConversation(unittest.TestCase):
    def test_multi_turn_conversation(self):
        from linhai.tui.messages_list import MessagesList

        user1 = _make_user_msg("what is 2+2?")
        gen1 = _make_generation_widget(
            segments=[
                NormalSegment(segment_type="normal", content="4", is_finished=True)
            ]
        )
        user2 = _make_user_msg("thanks!")
        ml = object.__new__(MessagesList)
        ml.messages = [user1, gen1, user2]
        result = ml.serialize()
        self.assertEqual(len(result["messages"]), 3)
        self.assertEqual(result["messages"][0]["type"], "user")
        self.assertEqual(result["messages"][1]["type"], "assistant")
        self.assertEqual(result["messages"][2]["type"], "user")


class TestRestoreFrom(unittest.TestCase):
    def test_restore_skips_unknown_type(self):
        from linhai.tui.messages_list import MessagesList

        ml = object.__new__(MessagesList)
        ml.messages = []
        ml.pygments_theme = "lightbulb"
        ml.get_refresh_interval = lambda: 0.1
        ml.mount = mock.MagicMock()
        data = {"messages": [{"type": "unknown_type"}]}
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


class TestSegmentDictContract(unittest.TestCase):
    def test_normal_segment_keys(self):
        seg = NormalSegment(segment_type="normal", content="text", is_finished=True)
        d = dict(seg)
        self.assertEqual(d["segment_type"], "normal")
        self.assertIn("content", d)
        self.assertIn("is_finished", d)

    def test_toolcall_segment_keys(self):
        seg = ToolCallSegment(
            segment_type="toolcall",
            raw="{}",
            is_finished=True,
            is_corrupted=False,
            markdown_representation="- name: `test`",
            tool_name="test",
        )
        d = dict(seg)
        self.assertIn("raw", d)
        self.assertIn("tool_name", d)
        self.assertIn("is_corrupted", d)
        self.assertIn("markdown_representation", d)

    def test_reasoning_segment_keys(self):
        seg = ReasoningSegment(
            segment_type="reasoning", content="thinking", is_finished=True
        )
        d = dict(seg)
        self.assertIn("content", d)
