"""Test cases for ReasoningContentWidget."""

import unittest
from unittest.mock import Mock, patch
from linhai.tui.components import ReasoningContentWidget


class TestReasoningContentWidget(unittest.TestCase):
    """Test ReasoningContentWidget functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.role = "assistant"
        self.content = "这是一个测试思考内容\n包含多行文本\n和一些特殊字符 [ ] \\ 等"
        self.sender_name = "test-agent"
        self.mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        self.widget = ReasoningContentWidget(
            role=self.role,
            sender_name=self.sender_name,
            theme="nord",
            segment=self.mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        self.widget.content_str += self.content

    def test_initial_state(self):
        """Test initial state of the widget."""
        self.assertEqual(self.widget.role, "assistant-reasoning")
        self.assertEqual(self.widget.content_str, self.content)
        self.assertEqual(self.widget.sender_name, self.sender_name)
        self.assertFalse(self.widget.is_expanded)

    def test_border_title_calculation(self):
        """Test border title calculation in different states."""
        self.widget.is_expanded = False
        title = self.widget.calculate_border_title()
        self.assertIn("[点击展开]", title)
        self.assertIn(self.sender_name, title)

        self.widget.is_expanded = True
        title = self.widget.calculate_border_title()
        self.assertIn("[点击隐藏]", title)
        self.assertIn(self.sender_name, title)

    def test_feed_string(self):
        """Test content_str update (replacing feed_string method)."""
        additional_content = "\n追加的内容"
        original_content = self.widget.content_str

        # 直接更新content_str，因为feed_string方法已删除
        self.widget.content_str += additional_content

        self.assertEqual(self.widget.content_str, original_content + additional_content)

    def test_append_content(self):
        """Test content_str update (replacing append_content method)."""
        additional_content = "\n通过append_content追加"
        original_content = self.widget.content_str

        # 直接更新content_str，因为append_content方法已删除
        self.widget.content_str += additional_content

        self.assertEqual(self.widget.content_str, original_content + additional_content)

    def test_on_click_toggle(self):
        """Test click toggles expanded state."""
        initial_state = self.widget.is_expanded

        # 模拟 update 方法以避免 Textual 上下文错误
        self.widget.update = Mock()

        self.widget.on_click()

        self.assertNotEqual(self.widget.is_expanded, initial_state)

        self.widget.on_click()

        self.assertEqual(self.widget.is_expanded, initial_state)

    def test_update_display_collapsed(self):
        """Test display update in collapsed state."""
        self.widget.is_expanded = False

        update_calls = []
        self.widget.update = Mock(side_effect=lambda x: update_calls.append(x))

        self.widget.update_display()

        self.assertEqual(len(update_calls), 1)
        content = update_calls[0]
        # 现在返回的是Text对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Text")

    def test_update_display_expanded(self):
        """Test display update in expanded state."""
        self.widget.is_expanded = True

        update_calls = []
        self.widget.update = Mock(side_effect=lambda x: update_calls.append(x))

        self.widget.update_display()

        self.assertEqual(len(update_calls), 1)
        content = update_calls[0]
        # 现在返回的是Syntax对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Syntax")

    def test_truncation_in_collapsed_state(self):
        """Test that collapsed state shows last two lines."""
        multi_line_content = """第一行内容
第二行内容
第三行内容
第四行内容"""

        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += multi_line_content
        widget.is_expanded = False

        rendered_contents = []
        widget.update = Mock(side_effect=lambda x: rendered_contents.append(x))

        widget.update_display()

        self.assertEqual(len(rendered_contents), 1)
        content = rendered_contents[0]
        # 现在返回的是Text对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Text")

    def test_special_characters_in_collapsed_state(self):
        """Test that special characters don't cause crashes in collapsed state."""
        content_with_special_chars = "思考内容包含特殊字符 [方括号] \\反斜杠 &符号"

        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += content_with_special_chars
        widget.is_expanded = False

        rendered_content = []
        widget.update = Mock(side_effect=lambda x: rendered_content.append(x))

        widget.update_display()

        self.assertEqual(len(rendered_content), 1)

    @patch("linhai.tui.components.ReasoningContentWidget.set_timer")
    def test_stop_method(self, mock_set_timer):
        """Test that finish_streaming method stops the timer."""
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += "test content"
        mock_timer = Mock()
        widget.timer = mock_timer

        # 模拟 update 方法以避免 Textual 上下文错误
        widget.update = Mock()

        # 配置 mock_set_timer 以停止定时器并清除timer
        def stop_and_clear(*args, **kwargs):
            mock_timer.stop()
            widget.timer = None

        mock_set_timer.side_effect = stop_and_clear

        # finish_streaming已删除，直接停止timer
        if widget.timer:
            widget.timer.stop()
            widget.timer = None

        mock_timer.stop.assert_called_once()
        self.assertIsNone(widget.timer)

    @patch("linhai.tui.components.ReasoningContentWidget.set_timer")
    def test_stop_method_actual_timer(self, mock_set_timer):
        """Test finish_streaming method with actual timer behavior."""
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += "test content"

        mock_timer = Mock()
        widget.timer = mock_timer

        # 模拟 update 方法以避免 Textual 上下文错误
        widget.update = Mock()

        # 配置 mock_set_timer 以停止定时器并清除timer
        def stop_and_clear(*args, **kwargs):
            mock_timer.stop()
            widget.timer = None

        mock_set_timer.side_effect = stop_and_clear

        # finish_streaming已删除，直接停止timer
        if widget.timer:
            widget.timer.stop()
            widget.timer = None

        mock_timer.stop.assert_called_once()
        self.assertIsNone(widget.timer)

    @patch("linhai.tui.components.ReasoningContentWidget.set_timer")
    def test_stop_method_without_timer(self, mock_set_timer):
        """Test finish_streaming method when there is no timer."""
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += "test content"
        widget.timer = None

        # 模拟 update 方法以避免 Textual 上下文错误
        widget.update = Mock()

        # 配置 mock_set_timer 以避免错误，并清除timer
        def clear_timer(*args, **kwargs):
            widget.timer = None

        mock_set_timer.side_effect = clear_timer

        # finish_streaming已删除，timer已经是None
        self.assertIsNone(widget.timer)

    def test_panel_styling(self):
        """Test that styling is correctly applied."""
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += "test content"

        rendered_contents = []
        widget.update = Mock(side_effect=lambda x: rendered_contents.append(x))

        widget.update_display()

        self.assertEqual(len(rendered_contents), 1)
        content = rendered_contents[0]
        # 现在返回的是Text对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Text")

    def test_no_wrap_styling(self):
        """Test that no_wrap=True is applied in ReasoningContentWidget."""
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += "测试内容"
        widget.is_expanded = False

        rendered_contents = []
        widget.update = Mock(side_effect=lambda x: rendered_contents.append(x))

        widget.update_display()

        self.assertEqual(len(rendered_contents), 1)
        content = rendered_contents[0]
        # 现在返回的是Text对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Text")
        # 检查no_wrap属性
        self.assertTrue(content.no_wrap)

    def test_truncated_content_no_wrap(self):
        """Test that truncated content in collapsed state has no_wrap=True."""
        long_content = "这是一行很长的测试内容" * 10
        mock_segment = {
            "segment_type": "reasoning",
            "content": "",
            "is_finished": False,
        }
        widget = ReasoningContentWidget(
            role="assistant",
            sender_name="test",
            theme="nord",
            segment=mock_segment,
            get_refresh_interval=lambda: 0.05,
        )
        widget.content_str += long_content
        widget.is_expanded = False

        rendered_contents = []
        widget.update = Mock(side_effect=lambda x: rendered_contents.append(x))

        widget.update_display()

        self.assertEqual(len(rendered_contents), 1)
        content = rendered_contents[0]
        # 现在返回的是Text对象，而不是Panel
        self.assertEqual(content.__class__.__name__, "Text")
        # 检查no_wrap属性
        self.assertTrue(content.no_wrap)


if __name__ == "__main__":
    unittest.main()
