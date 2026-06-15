import asyncio
import unittest

from textual.app import App, ComposeResult
from linhai.tui.components import NormalContentWidget
from linhai.parsed_message import NormalSegment


def _make_segment(content: str, is_finished: bool) -> NormalSegment:
    return NormalSegment(
        segment_type="normal", content=content, is_finished=is_finished
    )


class _TestApp(App):
    def __init__(self, segment: NormalSegment, **kwargs):
        super().__init__(**kwargs)
        self._segment = segment

    def compose(self) -> ComposeResult:
        yield NormalContentWidget(
            role="assistant",
            sender_name="test-agent",
            pygments_theme="nord",
            segment=self._segment,
            get_refresh_interval=lambda: 1.0,
        )


class TestNormalContentWidget(unittest.IsolatedAsyncioTestCase):
    async def test_widget_mounts_with_segment(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            self.assertEqual(widget._segment["content"], "hello")
            self.assertFalse(widget._segment["is_finished"])

    async def test_content_is_empty_with_blank(self):
        segment = _make_segment("   ", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            self.assertTrue(widget.content_is_empty())

    async def test_content_is_not_empty_after_stream(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            await widget.update_display()
            self.assertFalse(widget.content_is_empty())

    async def test_streaming_updates_streamed_content(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            segment["content"] = "hello world"
            await widget.update_display()
            self.assertEqual(widget._streamed_content, "hello world")

    async def test_finished_cleans_up_stream(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            segment["content"] = "completed"
            segment["is_finished"] = True
            await widget.update_display()
            self.assertIsNone(widget._stream)
            self.assertEqual(widget._streamed_content, "completed")

    async def test_no_update_when_content_unchanged(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            await widget.update_display()
            self.assertEqual(widget._streamed_content, "hello")
            await widget.update_display()
            self.assertEqual(widget._streamed_content, "hello")

    async def test_segment_unchanged_but_finished(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            segment["is_finished"] = True
            await widget.update_display()
            self.assertIsNone(widget._stream)
            self.assertEqual(widget._streamed_content, "hello")

    async def test_empty_segment_stays_empty(self):
        segment = _make_segment("", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            self.assertEqual(widget._streamed_content, "")
            await widget.update_display()
            self.assertEqual(widget._streamed_content, "")


class TestNormalContentWidgetEdgeCases(unittest.TestCase):
    def test_content_empty_initially(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertTrue(widget.content_is_empty())
        self.assertEqual(widget._streamed_content, "")

    def test_role_class_present(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertIn("assistant-message", widget.classes)

    def test_widget_has_border_title(self):
        segment = _make_segment("hello", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="bot",
            pygments_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertEqual(widget.border_title, "bot")

    def test_content_is_empty_after_empty_streaming(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        widget._streamed_content = "  \t\n  "
        self.assertTrue(widget.content_is_empty())


if __name__ == "__main__":
    unittest.main()
