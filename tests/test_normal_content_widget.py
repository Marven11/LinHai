import asyncio
import unittest
from unittest.mock import AsyncMock, Mock
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
            config_theme="nord",
            segment=self._segment,
            get_refresh_interval=lambda: 1.0,
        )


class TestNormalContentWidgetStreaming(unittest.TestCase):
    def test_on_mount_creates_stream(self):
        asyncio.run(self._test_on_mount_creates_stream())

    async def _test_on_mount_creates_stream(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)
            self.assertIsNotNone(widget._stream)

    def test_stream_write_on_new_content(self):
        asyncio.run(self._test_stream_write())

    async def _test_stream_write(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)

            segment["content"] = "hello world"
            write_mock = AsyncMock()
            widget._stream.write = write_mock
            await widget.update_display()

            write_mock.assert_awaited_once_with("hello world")
            self.assertEqual(widget._streamed_content, "hello world")

    def test_no_write_when_content_unchanged(self):
        asyncio.run(self._test_no_write())

    async def _test_no_write(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)

            await widget.update_display()

            write_mock = AsyncMock()
            widget._stream.write = write_mock

            await widget.update_display()

            write_mock.assert_not_awaited()

    def test_finished_stops_stream_and_full_update(self):
        asyncio.run(self._test_finished())

    async def _test_finished(self):
        segment = _make_segment("hello", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)

            segment["content"] = "hello world"
            segment["is_finished"] = True

            update_mock = Mock()
            widget.update = update_mock

            await widget.update_display()

            self.assertIsNone(widget._stream)
            update_mock.assert_called_once_with("hello world")

    def test_finished_unchanged_content(self):
        asyncio.run(self._test_finished_unchanged())

    async def _test_finished_unchanged(self):
        segment = _make_segment("hello", is_finished=True)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(NormalContentWidget)

            write_mock = AsyncMock()
            widget._stream.write = write_mock
            update_mock = Mock()
            widget.update = update_mock

            await widget.update_display()

            self.assertIsNone(widget._stream)
            update_mock.assert_called_once_with("hello")
            write_mock.assert_not_awaited()

    def test_content_is_empty(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertTrue(widget.content_is_empty())

    def test_content_is_not_empty(self):
        segment = _make_segment("hello", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        widget._streamed_content = "hello"
        self.assertFalse(widget.content_is_empty())

    def test_stop_timer(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        mock_timer = Mock()
        widget.timer = mock_timer
        widget.stop_timer()
        mock_timer.stop.assert_called_once()


class TestNormalContentWidgetInitial(unittest.TestCase):
    def test_initial_streamed_content_empty(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertEqual(widget._streamed_content, "")
        self.assertIsNone(widget._stream)

    def test_role_class_added(self):
        segment = _make_segment("", is_finished=False)
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme="nord",
            segment=segment,
            get_refresh_interval=lambda: 1.0,
        )
        self.assertIn("assistant-message", widget.classes)


if __name__ == "__main__":
    unittest.main()
