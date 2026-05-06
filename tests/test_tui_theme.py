import unittest
from unittest.mock import Mock

from linhai.config import TUIConfig
from linhai.tui.components import (
    _syntax_or_text,
    ToolCallWidget,
    ReasoningContentWidget,
    UserMessageWidget,
    NormalContentWidget,
    MessageWidget,
)


class TestTUIConfigTheme(unittest.TestCase):
    def test_theme_defaults_to_none(self):
        config = TUIConfig()
        self.assertIsNone(config.theme)

    def test_theme_accepts_string(self):
        config = TUIConfig(theme="nord")
        self.assertEqual(config.theme, "nord")

    def test_theme_accepts_none(self):
        config = TUIConfig(theme=None)
        self.assertIsNone(config.theme)


class TestSyntaxOrText(unittest.TestCase):
    def test_returns_syntax_with_theme(self):
        result = _syntax_or_text("print('hello')", "python", "nord")
        self.assertEqual(result.__class__.__name__, "Syntax")

    def test_returns_text_without_theme(self):
        result = _syntax_or_text("print('hello')", "python", None)
        self.assertEqual(result.__class__.__name__, "Text")


class TestWidgetsWithNoneTheme(unittest.TestCase):
    def test_toolcall_widget_accepts_none_theme(self):
        segment = {
            "segment_type": "toolcall",
            "raw": "",
            "is_finished": False,
            "is_corrupted": False,
            "markdown_representation": "",
            "tool_name": "",
        }
        widget = ToolCallWidget(
            config_theme=None, segment=segment, get_refresh_interval=lambda: 0.05
        )
        self.assertIsNone(widget.config_theme)

    def test_reasoning_widget_accepts_none_theme(self):
        segment = {"segment_type": "reasoning", "content": "", "is_finished": False}
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            config_theme=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertIsNone(widget.config_theme)

    def test_user_message_widget_accepts_none_theme(self):
        widget = UserMessageWidget(
            content="hello", sender_name="user", config_theme=None
        )
        self.assertIsNone(widget.config_theme)

    def test_normal_content_widget_accepts_none_theme(self):
        segment = {"segment_type": "normal", "content": "", "is_finished": False}
        widget = NormalContentWidget(
            role="assistant",
            sender_name="test",
            config_theme=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.assertIsNone(widget.config_theme)

    def test_toolcall_renders_text_with_none_theme(self):
        segment = {
            "segment_type": "toolcall",
            "raw": '{"name": "test"}',
            "is_finished": False,
            "is_corrupted": False,
            "markdown_representation": "- name: `test`",
            "tool_name": "test",
        }
        widget = ToolCallWidget(
            config_theme=None, segment=segment, get_refresh_interval=lambda: 0.05
        )
        widget.update = Mock()
        widget.update_display()
        update_args = widget.update.call_args_list
        for call in update_args:
            renderable = call[0][0]
            self.assertEqual(renderable.__class__.__name__, "Text")

    def test_reasoning_renders_text_with_none_theme(self):
        segment = {"segment_type": "reasoning", "content": "", "is_finished": False}
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            config_theme=None,
            segment=segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str = "thinking content"
        widget.is_expanded = True
        widget.update = Mock()
        widget.update_display()
        renderable = widget.update.call_args[0][0]
        self.assertEqual(renderable.__class__.__name__, "Text")


if __name__ == "__main__":
    unittest.main()
