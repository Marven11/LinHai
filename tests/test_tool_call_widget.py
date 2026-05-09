import unittest
import asyncio
from unittest.mock import patch
from textual.app import App, ComposeResult
from textual.widgets import Markdown
from linhai.tui.components import ToolCallWidget, _ToolCallCollapseHeader
from linhai.parsed_message import ToolCallSegment
from linhai.utils.i18n import t


def _make_segment(
    raw: str, is_finished: bool, is_corrupted: bool = False
) -> ToolCallSegment:
    return ToolCallSegment(
        segment_type="toolcall",
        raw=raw,
        is_finished=is_finished,
        is_corrupted=is_corrupted,
        markdown_representation=BAD_TOOLCALL if is_corrupted else "",
        tool_name="",
    )


BAD_TOOLCALL = "<bad toolcall>"


class _TestApp(App):
    def __init__(self, segment: ToolCallSegment, **kwargs):
        super().__init__(**kwargs)
        self._segment = segment

    def compose(self) -> ComposeResult:
        widget = ToolCallWidget(
            pygments_theme="monokai",
            syntax_background=None,
            segment=self._segment,
            get_refresh_interval=lambda: 1.0,
        )
        widget.is_collapsed = True
        yield widget


class TestToolCallWidgetMarkdown(unittest.TestCase):
    def test_expand_finished_mounts_markdown(self):
        asyncio.run(self._test_expand_finished())

    async def _test_expand_finished(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        seg["tool_name"] = "test"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 1)
            self.assertIsNotNone(widget._markdown_widget)

    def test_expand_unfinished_uses_syntax(self):
        asyncio.run(self._test_expand_unfinished())

    async def _test_expand_unfinished(self):
        seg = _make_segment('{"name": "test", "arguments":', is_finished=False)
        seg["markdown_representation"] = "- name: `test`\n- arguments: `"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 0)
            self.assertIsNone(widget._markdown_widget)

    def test_collapse_removes_markdown(self):
        asyncio.run(self._test_collapse_removes())

    async def _test_collapse_removes(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertIsNotNone(widget._markdown_widget)
            widget._collapse()
            self.assertIsNone(widget._markdown_widget)
            self.assertTrue(widget.is_collapsed)

    def test_expand_finished_mounts_collapse_header(self):
        asyncio.run(self._test_expand_finished_mounts_header())

    async def _test_expand_finished_mounts_header(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            headers = widget.query(_ToolCallCollapseHeader)
            self.assertEqual(len(headers), 1)
            self.assertIsNotNone(widget._collapse_header)

    def test_collapse_removes_header(self):
        asyncio.run(self._test_collapse_removes_header())

    async def _test_collapse_removes_header(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertIsNotNone(widget._collapse_header)
            widget._collapse()
            self.assertIsNone(widget._collapse_header)

    def test_expand_finished_border_title_no_hint(self):
        asyncio.run(self._test_expand_finished_border_title())

    async def _test_expand_finished_border_title(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(widget.border_title, "tool call")

    def test_expand_unfinished_border_title_has_hint(self):
        asyncio.run(self._test_expand_unfinished_border_title())

    @patch("linhai.utils.i18n.locale.getlocale")
    async def _test_expand_unfinished_border_title(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        seg = _make_segment('{"name": "test", "arguments":', is_finished=False)
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(
                widget.border_title,
                t({"zh_CN": "tool call [点击隐藏]", "en": "tool call [click to hide]"}),
            )

    def test_click_does_not_collapse_when_finished(self):
        asyncio.run(self._test_click_no_collapse_finished())

    async def _test_click_no_collapse_finished(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            widget.on_click()
            self.assertFalse(widget.is_collapsed)

    def test_click_collapses_when_unfinished(self):
        asyncio.run(self._test_click_collapses_unfinished())

    async def _test_click_collapses_unfinished(self):
        seg = _make_segment('{"name": "test", "arguments":', is_finished=False)
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            widget.on_click()
            self.assertTrue(widget.is_collapsed)

    def test_click_collapses_when_error(self):
        asyncio.run(self._test_click_collapses_error())

    async def _test_click_collapses_error(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
            is_corrupted=True,
        )
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            widget.on_click()
            self.assertTrue(widget.is_collapsed)

    def test_collapse_border_title_has_expand_hint(self):
        asyncio.run(self._test_collapse_border_title())

    @patch("linhai.utils.i18n.locale.getlocale")
    async def _test_collapse_border_title(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
        )
        seg["markdown_representation"] = "- name: `test`\n"
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            widget._collapse()
            self.assertEqual(
                widget.border_title,
                t(
                    {
                        "zh_CN": "tool call [点击展开]",
                        "en": "tool call [click to expand]",
                    }
                ),
            )

    def test_error_uses_syntax(self):
        asyncio.run(self._test_expand_error())

    async def _test_expand_error(self):
        seg = _make_segment(
            '{"name": "test", "arguments": {"key": "val"}}',
            is_finished=True,
            is_corrupted=True,
        )
        async with _TestApp(seg).run_test() as pilot:
            widget = pilot.app.query_one(ToolCallWidget)
            widget._expand()
            self.assertEqual(len(widget.query(Markdown)), 0)
            self.assertIsNone(widget._markdown_widget)


if __name__ == "__main__":
    unittest.main()
