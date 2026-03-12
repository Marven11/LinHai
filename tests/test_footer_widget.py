"""Tests for FooterWidget component."""

import unittest
from unittest.mock import MagicMock, patch
from linhai.group_chat import GroupChat
from linhai.token_manager import TokenManager


class TestFooterWidget(unittest.TestCase):
    """Test cases for FooterWidget."""

    def setUp(self):
        """Set up test fixtures."""
        self.group_chat = GroupChat()
        self.token_manager = TokenManager(self.group_chat)

    def test_footer_widget_init(self):
        """Test FooterWidget initialization."""
        from linhai.cli.components import FooterWidget

        widget = FooterWidget(
            group_chat=self.group_chat,
            token_manager=self.token_manager,
            use_nerd_font=False,
        )

        self.assertEqual(widget.group_chat, self.group_chat)
        self.assertEqual(widget.token_manager, self.token_manager)
        self.assertFalse(widget.use_nerd_font)

    def test_footer_widget_with_nerd_font(self):
        """Test FooterWidget with nerd font enabled."""
        from linhai.cli.components import FooterWidget

        widget = FooterWidget(
            group_chat=self.group_chat,
            token_manager=self.token_manager,
            use_nerd_font=True,
        )

        self.assertTrue(widget.use_nerd_font)


if __name__ == "__main__":
    unittest.main()
