import unittest
import asyncio
from unittest.mock import MagicMock
from textual.app import App, ComposeResult

from linhai.tui.components import (
    MessageWidget,
    ToolCallWidget,
    ReasoningContentWidget,
)


def _make_toolcall_segment(name, is_finished=True):
    return {
        "segment_type": "toolcall",
        "content": f'{{"name": "{name}", "arguments": {{}}}}',
        "is_finished": is_finished,
    }


def _mount_toolcall(msg, name, is_finished=True, has_error=False):
    tc = ToolCallWidget(
        theme=None,
        segment=_make_toolcall_segment(name, is_finished=is_finished),
        get_refresh_interval=lambda: 1.0,
    )
    tc.json_str = tc._segment["content"]
    tc.tool_name = name
    if has_error:
        tc.has_error = True
    msg._content.mount(tc)
    return tc


def _make_reasoning_segment(content="thinking...", is_finished=True):
    return {
        "segment_type": "reasoning",
        "content": content,
        "is_finished": is_finished,
    }


class _MessageTestApp(App):
    def compose(self) -> ComposeResult:
        mock_parsed = MagicMock()
        mock_parsed.segment_queue = asyncio.Queue()
        widget = MessageWidget(
            role="assistant",
            sender_name="test",
            theme=None,
            parsed_answer=mock_parsed,
            get_refresh_interval=lambda: 1.0,
        )
        yield widget


def _make_toolcall_segment_with_error(is_finished=True):
    seg = _make_toolcall_segment("bad_call", is_finished=is_finished)
    seg["content"] = "{invalid json"
    return seg


class TestGetExpandHeaderText(unittest.TestCase):
    def test_only_finished_non_error_tools_shown(self):
        asyncio.run(self._test_only_finished_non_error())

    async def _test_only_finished_non_error(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            _mount_toolcall(msg, "write_file", is_finished=False)
            _mount_toolcall(msg, "bad_call", has_error=True)
            header_text = msg._get_expand_header_text()
            self.assertIn("read_file", header_text)
            self.assertNotIn("write_file", header_text)
            self.assertNotIn("bad_call", header_text)

    def test_no_tools_returns_empty(self):
        asyncio.run(self._test_no_tools_returns_empty())

    async def _test_no_tools_returns_empty(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            header_text = msg._get_expand_header_text()
            self.assertEqual(header_text.plain, "\u25bc ")

    def test_clustered_tool_names_in_header(self):
        asyncio.run(self._test_clustered_names())

    async def _test_clustered_names(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            for name in ["read_file", "read_file", "list_files"]:
                _mount_toolcall(msg, name)
            header_text = msg._get_expand_header_text()
            self.assertIn("read_file*2", header_text)
            self.assertIn("list_files", header_text)


class TestExpandMessageShowsToolNames(unittest.TestCase):
    def test_expand_header_shows_tool_names(self):
        asyncio.run(self._test_expand_header_tool_names())

    async def _test_expand_header_tool_names(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            msg._auto_transition()
            self.assertEqual(msg._state, "collapsed")
            msg._expand_message()
            self.assertEqual(msg._state, "expanded")
            header_text = msg._get_expand_header_text()
            self.assertIn("read_file", header_text)


class TestStreamingHeader(unittest.TestCase):
    def test_streaming_header_shows_when_finished_tools_exist(self):
        asyncio.run(self._test_streaming_header_visible())

    async def _test_streaming_header_visible(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            self.assertEqual(msg._state, "streaming")
            _mount_toolcall(msg, "read_file")
            msg._update_streaming_header()
            self.assertTrue(msg._expand_header.display)
            header_text = msg._get_expand_header_text()
            self.assertIn("read_file", header_text)

    def test_streaming_header_hidden_when_no_finished_tools(self):
        asyncio.run(self._test_streaming_header_hidden())

    async def _test_streaming_header_hidden(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            self.assertEqual(msg._state, "streaming")
            msg._update_streaming_header()
            self.assertFalse(msg._expand_header.display)

    def test_streaming_timer_stops_on_collapse(self):
        asyncio.run(self._test_timer_stops())

    async def _test_timer_stops(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            msg._update_streaming_header()
            self.assertTrue(msg._expand_header.display)
            msg._collapse_message()
            msg._update_streaming_header()
            self.assertIsNone(msg._streaming_timer)


class TestMessageCollapseInteraction(unittest.TestCase):
    def test_tool_calls_collapsed_to_clustered_summary(self):
        asyncio.run(self._test_tool_calls_collapsed())

    async def _test_tool_calls_collapsed(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            for name in [
                "read_file",
                "read_file",
                "list_files",
                "read_file",
                "read_file",
            ]:
                _mount_toolcall(msg, name)

            msg._auto_transition()
            self.assertEqual(msg._state, "collapsed")
            summary = msg._get_tool_call_summary()
            self.assertIn("read_file*4", summary)
            self.assertIn("list_files", summary)

    def test_click_collapsed_expands_message(self):
        asyncio.run(self._test_click_collapsed_expands())

    async def _test_click_collapsed_expands(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            msg._auto_transition()
            self.assertEqual(msg._state, "collapsed")

            msg._expand_message()
            self.assertEqual(msg._state, "expanded")
            self.assertFalse(msg._collapsed_view.display)
            self.assertTrue(msg._expand_header.display)
            self.assertTrue(msg._content.display)

    def test_expand_tool_then_collapse_message_hides_tool(self):
        asyncio.run(self._test_expand_tool_collapse_message())

    async def _test_expand_tool_collapse_message(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            msg._auto_transition()
            msg._expand_message()
            self.assertEqual(msg._state, "expanded")

            msg._content.children[0]._expand()
            self.assertFalse(msg._content.children[0].is_collapsed)

            msg._collapse_message()
            self.assertEqual(msg._state, "collapsed")
            self.assertFalse(msg._content.display)

    def test_click_reasoning_does_not_collapse_message(self):
        asyncio.run(self._test_click_reasoning())

    async def _test_click_reasoning(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            _mount_toolcall(msg, "read_file")
            rc = ReasoningContentWidget(
                role="assistant",
                sender_name="test",
                theme=None,
                segment=_make_reasoning_segment("thinking content"),
                get_refresh_interval=lambda: 1.0,
            )
            msg._content.mount(rc)

            msg._auto_transition()
            msg._expand_message()
            self.assertEqual(msg._state, "expanded")

            rc.on_click()
            self.assertTrue(rc.is_expanded)

            rc.on_click()
            self.assertFalse(rc.is_expanded)
            self.assertEqual(msg._state, "expanded")


if __name__ == "__main__":
    unittest.main()
