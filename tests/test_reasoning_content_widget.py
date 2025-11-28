"""Test cases for ReasoningContentWidget."""

import unittest
from unittest.mock import Mock
from linhai.cli.components import ReasoningContentWidget


class TestReasoningContentWidget(unittest.TestCase):
    """Test ReasoningContentWidget functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.role = "assistant"
        self.content = "这是一个测试思考内容\n包含多行文本\n和一些特殊字符 [ ] \\ 等"
        self.sender_name = "test-agent"
        self.widget = ReasoningContentWidget(
            role=self.role,
            content=self.content,
            sender_name=self.sender_name
        )

    def test_initial_state(self):
        """Test initial state of the widget."""
        self.assertEqual(self.widget.role, "assistant-reasoning")
        self.assertEqual(self.widget.content_str, self.content)
        self.assertEqual(self.widget.sender_name, self.sender_name)
        self.assertFalse(self.widget.is_expanded)
        self.assertIn("reasoning-widget", self.widget.classes)

    def test_border_title_calculation(self):
        """Test border title calculation in different states."""
        # Collapsed state
        self.widget.is_expanded = False
        title = self.widget.calculate_border_title()
        self.assertIn("[点击展开]", title)
        self.assertIn(self.sender_name, title)

        # Expanded state
        self.widget.is_expanded = True
        title = self.widget.calculate_border_title()
        self.assertIn("[点击隐藏]", title)
        self.assertIn(self.sender_name, title)

    def test_feed_string(self):
        """Test appending content to the widget."""
        additional_content = "\n追加的内容"
        original_content = self.widget.content_str
        
        self.widget.feed_string(additional_content)
        
        self.assertEqual(self.widget.content_str, original_content + additional_content)

    def test_append_content(self):
        """Test append_content method (compatibility)."""
        additional_content = "\n通过append_content追加"
        original_content = self.widget.content_str
        
        self.widget.append_content(additional_content)
        
        self.assertEqual(self.widget.content_str, original_content + additional_content)

    def test_on_click_toggle(self):
        """Test click toggles expanded state."""
        initial_state = self.widget.is_expanded
        
        self.widget.on_click()
        
        self.assertNotEqual(self.widget.is_expanded, initial_state)
        
        # Toggle again
        self.widget.on_click()
        
        self.assertEqual(self.widget.is_expanded, initial_state)

    def test_update_display_collapsed(self):
        """Test display update in collapsed state."""
        self.widget.is_expanded = False
        
        # Mock the update method to capture what would be rendered
        update_calls = []
        self.widget.update = Mock(side_effect=lambda x: update_calls.append(x))
        
        self.widget.update_display()
        
        # Should have one call to update with a Text (no Panel in collapsed state)
        self.assertEqual(len(update_calls), 1)
        text = update_calls[0]
        self.assertEqual(text.__class__.__name__, "Text")

    def test_update_display_expanded(self):
        """Test display update in expanded state."""
        self.widget.is_expanded = True
        
        # Mock the update method to capture what would be rendered
        update_calls = []
        self.widget.update = Mock(side_effect=lambda x: update_calls.append(x))
        
        self.widget.update_display()
        
        # Should have one call to update with a Syntax
        self.assertEqual(len(update_calls), 1)
        syntax = update_calls[0]
        self.assertEqual(syntax.__class__.__name__, "Syntax")

    def test_truncation_in_collapsed_state(self):
        """Test that collapsed state shows last two lines."""
        multi_line_content = """第一行内容
第二行内容
第三行内容
第四行内容"""
        
        widget = ReasoningContentWidget(
            role="assistant",
            content=multi_line_content,
            sender_name="test"
        )
        widget.is_expanded = False
        
        # Mock update to capture the rendered content
        rendered_content = []
        widget.update = Mock(side_effect=lambda x: rendered_content.append(x))
        
        widget.update_display()
        
        # Should render a Text with truncated content (last two lines)
        self.assertEqual(len(rendered_content), 1)
        text = rendered_content[0]
        self.assertEqual(text.__class__.__name__, "Text")
        # Verify it contains the last two lines content
        text_str = str(text)
        self.assertIn("第三行内容", text_str)
        self.assertIn("第四行内容", text_str)

    def test_special_characters_in_collapsed_state(self):
        """Test that special characters don't cause crashes in collapsed state."""
        content_with_special_chars = "思考内容包含特殊字符 [方括号] \\反斜杠 &符号"
        
        widget = ReasoningContentWidget(
            role="assistant",
            content=content_with_special_chars,
            sender_name="test"
        )
        widget.is_expanded = False
        
        # Mock update to capture the rendered content
        rendered_content = []
        widget.update = Mock(side_effect=lambda x: rendered_content.append(x))
        
        # This should not raise any exceptions
        widget.update_display()
        
        self.assertEqual(len(rendered_content), 1)
        text = rendered_content[0]
        self.assertEqual(text.__class__.__name__, "Text")
        # Verify special characters are properly escaped
        self.assertIn("\\", str(text))


if __name__ == "__main__":
    unittest.main()