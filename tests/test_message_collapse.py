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
                tc = ToolCallWidget(
                    theme=None,
                    segment=_make_toolcall_segment(name),
                    get_refresh_interval=lambda: 1.0,
                )
                tc.json_str = tc._segment["content"]
                msg._content.mount(tc)

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
            tc = ToolCallWidget(
                theme=None,
                segment=_make_toolcall_segment("read_file"),
                get_refresh_interval=lambda: 1.0,
            )
            tc.json_str = tc._segment["content"]
            msg._content.mount(tc)
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
            tc = ToolCallWidget(
                theme=None,
                segment=_make_toolcall_segment("read_file"),
                get_refresh_interval=lambda: 1.0,
            )
            tc.json_str = tc._segment["content"]
            msg._content.mount(tc)
            msg._auto_transition()
            msg._expand_message()
            self.assertEqual(msg._state, "expanded")

            tc._expand()
            self.assertFalse(tc.is_collapsed)

            msg._collapse_message()
            self.assertEqual(msg._state, "collapsed")
            self.assertFalse(msg._content.display)

    def test_click_reasoning_does_not_collapse_message(self):
        asyncio.run(self._test_click_reasoning())

    async def _test_click_reasoning(self):
        async with _MessageTestApp().run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            tc = ToolCallWidget(
                theme=None,
                segment=_make_toolcall_segment("read_file"),
                get_refresh_interval=lambda: 1.0,
            )
            tc.json_str = tc._segment["content"]
            msg._content.mount(tc)
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
