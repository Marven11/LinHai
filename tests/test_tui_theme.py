import unittest
from unittest.mock import Mock

from linhai.config import TUIConfig
from linhai.tui.components import (
    ToolCallWidget,
    ReasoningContentWidget,
    UserMessageWidget,
    NormalContentWidget,
)


class TestTUIConfigTheme(unittest.TestCase):
    def test_textual_theme_defaults_to_none(self):
        config = TUIConfig()
        self.assertIsNone(config.textual_theme)

    def test_pygments_theme_defaults_to_lightbulb(self):
        config = TUIConfig()
        self.assertEqual(config.pygments_theme, "lightbulb")

    def test_textual_theme_accepts_string(self):
        config = TUIConfig(textual_theme="nord")
        self.assertEqual(config.textual_theme, "nord")

    def test_textual_theme_accepts_none(self):
        config = TUIConfig(textual_theme=None)
        self.assertIsNone(config.textual_theme)

    def test_pygments_theme_accepts_string(self):
        config = TUIConfig(pygments_theme="monokai")
        self.assertEqual(config.pygments_theme, "monokai")


class TestWidgetsAcceptPygmentsTheme(unittest.TestCase):
    def test_toolcall_widget_stores_theme(self):
        segment = {
            "segment_type": "toolcall",
            "raw": "",
            "is_finished": False,
            "is_corrupted": False,
            "markdown_representation": "",
            "tool_name": "",
        }
        widget = ToolCallWidget(
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertEqual(widget.pygments_theme, "nord")

    def test_reasoning_widget_stores_theme(self):
        segment = {"segment_type": "reasoning", "content": "", "is_finished": False}
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertEqual(widget.pygments_theme, "nord")

    def test_user_message_widget_stores_theme(self):
        widget = UserMessageWidget(
            content="hello", sender_name="user", pygments_theme="lightbulb"
        )
        self.assertEqual(widget.pygments_theme, "lightbulb")

    def test_normal_content_widget_stores_theme(self):
        segment = {"segment_type": "normal", "content": "", "is_finished": False}
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="lightbulb",
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertEqual(widget.pygments_theme, "lightbulb")

    def test_toolcall_renders_syntax_with_theme(self):
        segment = {
            "segment_type": "toolcall",
            "raw": '{"name": "test"}',
            "is_finished": False,
            "is_corrupted": False,
            "markdown_representation": "- name: `test`",
            "tool_name": "test",
        }
        widget = ToolCallWidget(
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.update = Mock()
        widget.update_display()
        update_args = widget.update.call_args_list
        for call in update_args:
            renderable = call[0][0]
            self.assertEqual(renderable.__class__.__name__, "Syntax")

    def test_reasoning_renders_syntax_with_theme(self):
        segment = {"segment_type": "reasoning", "content": "", "is_finished": False}
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            pygments_theme="nord",
            syntax_background=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str = "thinking content"
        widget.is_expanded = True
        widget.update = Mock()
        widget.update_display()
        renderable = widget.update.call_args[0][0]
        self.assertEqual(renderable.__class__.__name__, "Syntax")


if __name__ == "__main__":
    unittest.main()
