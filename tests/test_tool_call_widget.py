import unittest
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Markdown
from linhai.tui.components import ToolCallWidget
from linhai.parsed_message import Segment


def _make_segment(content: str, is_finished: bool) -> Segment:
    return Segment(segment_type="toolcall", content=content, is_finished=is_finished)


class _TestApp(App):
    def __init__(self, segment: Segment, **kwargs):
        super().__init__(**kwargs)
        self._segment = segment

    def compose(self) -> ComposeResult:
        widget = ToolCallWidget(
            theme="monokai",
            segment=self._segment,
            get_refresh_interval=lambda: 1.0,
        )
        widget.is_collapsed = True
        yield widget


class TestToolCallWidgetMarkdown(unittest.TestCase):
    def test_expand_finished_mounts_markdown(self):
        asyncio.run(self._test_expand_finished())

    async def _test_expand_finished(self):
        segment = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}', is_finished=True
        )
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 1)
            self.assertIsNotNone(widget._markdown_widget)

    def test_expand_unfinished_uses_syntax(self):
        asyncio.run(self._test_expand_unfinished())

    async def _test_expand_unfinished(self):
        segment = _make_segment('{"name": "test", "arguments":', is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 0)
            self.assertIsNone(widget._markdown_widget)

    def test_collapse_removes_markdown(self):
        asyncio.run(self._test_collapse_removes())

    async def _test_collapse_removes(self):
        segment = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}', is_finished=True
        )
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertIsNotNone(widget._markdown_widget)
            widget._collapse()
            self.assertIsNone(widget._markdown_widget)
            self.assertTrue(widget.is_collapsed)

    def test_expand_error_uses_syntax(self):
        asyncio.run(self._test_expand_error())

    async def _test_expand_error(self):
        segment = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}', is_finished=True
        )
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget.has_error = True
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 0)
            self.assertIsNone(widget._markdown_widget)


if __name__ == "__main__":
    unittest.main()
