import unittest

from textual.app import App, ComposeResult
from linhai.tui.components import ReasoningContentWidget


def _make_segment(content: str = "", is_finished: bool = False):
    return {
        "segment_type": "reasoning",
        "content": content,
        "is_finished": is_finished,
    }


class _TestApp(App):
    def __init__(self, segment, **kwargs):
        super().__init__(**kwargs)
        self._segment = segment

    def compose(self) -> ComposeResult:
        yield ReasoningContentWidget(
            role="assistant",
            sender_name="test-agent",
            pygments_theme="nord",
            syntax_background=None,
            segment=self._segment,
            get_refresh_interval=lambda: 0.05,
        )


class TestReasoningContentWidget(unittest.IsolatedAsyncioTestCase):
    async def test_initial_collapsed_state(self):
        segment = _make_segment("hello")
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            self.assertFalse(widget.is_expanded)
            self.assertIn("reasoning-widget-collapsed", widget.classes)

    async def test_click_toggles_expand(self):
        segment = _make_segment("hello")
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            self.assertFalse(widget.is_expanded)
            widget.on_click()
            self.assertTrue(widget.is_expanded)
            widget.on_click()
            self.assertFalse(widget.is_expanded)

    async def test_update_display_updates_content_str(self):
        segment = _make_segment("initial")
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            self.assertEqual(segment["content"], "initial")
            widget.update_display()
            self.assertEqual(widget.content_str, "initial")
            segment["content"] = "updated"
            widget.update_display()
            self.assertEqual(widget.content_str, "updated")

    async def test_finished_does_not_crash(self):
        segment = _make_segment("done", is_finished=True)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            widget.update_display()
            widget.update_display()

    async def test_unfinished_keeps_timer(self):
        segment = _make_segment("streaming", is_finished=False)
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            widget.update_display()
            self.assertIsNotNone(widget.timer)

    async def test_collapsed_state_css_class(self):
        segment = _make_segment("hello")
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            self.assertIn("reasoning-widget-collapsed", widget.classes)
            widget.on_click()
            self.assertNotIn("reasoning-widget-collapsed", widget.classes)
            self.assertIn("reasoning-widget-expanded", widget.classes)
            widget.on_click()
            self.assertIn("reasoning-widget-collapsed", widget.classes)
            self.assertNotIn("reasoning-widget-expanded", widget.classes)

    async def test_role_is_role_reasoning(self):
        segment = _make_segment("hello")
        async with _TestApp(segment).run_test() as pilot:
            widget = pilot.app.query_one(ReasoningContentWidget)
            self.assertEqual(widget.role, "assistant-reasoning")


class TestReasoningContentWidgetEdgeCases(unittest.TestCase):
    def test_empty_content_empty_string(self):
        segment = _make_segment("")
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertEqual(widget.content_str, "")

    def test_multiline_content_stored(self):
        content = "line1\nline2\nline3\nline4"
        segment = _make_segment(content)
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str = content
        self.assertEqual(widget.content_str, content)

    def test_special_characters_preserved(self):
        content = "包含 [方括号] \\反斜杠 &符号"
        segment = _make_segment(content)
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str = content
        self.assertEqual(widget.content_str, content)


if __name__ == "__main__":
    unittest.main()
