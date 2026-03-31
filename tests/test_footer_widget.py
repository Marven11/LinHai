"""Tests for FooterWidget component."""

import unittest
from unittest.mock import MagicMock, patch
from linhai.registry import Registry
from linhai.sandbox import BubbleWrapSandbox, NoSandbox, ProcessSandboxProtocol
from linhai.token_manager import TokenManager


class TestFooterWidget(unittest.TestCase):
    """Test cases for FooterWidget."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = Registry()
        self.token_manager = TokenManager(self.registry)

    def test_footer_widget_init(self):
        """Test FooterWidget initialization."""
        from linhai.cli.components import FooterWidget

        widget = FooterWidget(
            registry=self.registry,
            token_manager=self.token_manager,
            use_nerd_font=False,
        )

        self.assertEqual(widget.registry, self.registry)
        self.assertEqual(widget.token_manager, self.token_manager)
        self.assertFalse(widget.use_nerd_font)

    def test_footer_widget_with_nerd_font(self):
        """Test FooterWidget with nerd font enabled."""
        from linhai.cli.components import FooterWidget

        widget = FooterWidget(
            registry=self.registry,
            token_manager=self.token_manager,
            use_nerd_font=True,
        )

        self.assertTrue(widget.use_nerd_font)


class TestFooterWidgetSandboxIcon(unittest.TestCase):
    def _make_widget(self, sandbox, use_nerd_font=False):
        from linhai.cli.components import FooterWidget

        registry = Registry()
        token_manager = TokenManager(registry)
        registry.register_member("process_sandbox", sandbox)
        from linhai.agent import Agent

        mock_agent = MagicMock(spec=Agent)
        mock_agent.get_current_llm_info.return_value = ("test-llm", None)
        registry.register_member("agent", mock_agent)
        widget = FooterWidget(
            registry=registry,
            token_manager=token_manager,
            use_nerd_font=use_nerd_font,
        )
        widget.update = MagicMock()
        return widget

    def test_no_sandbox_no_icon(self):
        widget = self._make_widget(NoSandbox())
        widget.update_display()
        display_text = widget.update.call_args[0][0]
        self.assertNotIn("◭", display_text)

    def test_bubblewrap_sandbox_shows_icon(self):
        widget = self._make_widget(BubbleWrapSandbox(["bwrap"]))
        widget.update_display()
        display_text = widget.update.call_args[0][0]
        self.assertIn("◭", display_text)

    def test_sandbox_nerd_font_icon(self):
        widget = self._make_widget(BubbleWrapSandbox(["bwrap"]), use_nerd_font=True)
        widget.update_display()
        display_text = widget.update.call_args[0][0]
        self.assertNotIn("◭", display_text)

    def test_no_sandbox_nerd_font_no_icon(self):
        widget = self._make_widget(NoSandbox(), use_nerd_font=True)
        widget.update_display()
        display_text = widget.update.call_args[0][0]
        self.assertNotIn("\uf132", display_text)


if __name__ == "__main__":
    unittest.main()
