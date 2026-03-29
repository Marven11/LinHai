"""Tests for token_manager module."""

import unittest
from unittest.mock import MagicMock, patch
from linhai.token_manager import TokenManager
from linhai.registry import Registry
from linhai.llm import AnswerTokenUsage


class TestTokenManager(unittest.TestCase):
    """Test cases for TokenManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = Registry()
        self.token_manager = TokenManager(self.registry)

    def test_get_token_display_pieces_returns_list(self):
        """Test that get_token_display_pieces returns a list of strings."""
        # Setup mock agent
        mock_agent = MagicMock()
        mock_agent.orchestration.get_status_display_pieces.return_value = []
        mock_llm_instance = MagicMock()
        mock_llm_instance.get_token_limit.return_value = 8000
        mock_agent.get_current_llm_info.return_value = ("test-llm", mock_llm_instance)

        # Setup cumulative token usage
        self.token_manager.cumulative_token_usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cached_input_tokens": 25,
        }

        # Call the method
        result = self.token_manager.get_token_display_pieces(
            mock_agent, current_answer_token=0, use_nerd_font=False
        )

        # Verify it returns a list
        self.assertIsInstance(result, list)
        # Verify all items are strings
        for item in result:
            self.assertIsInstance(item, str)

    def test_get_token_display_pieces_empty_when_no_usage(self):
        """Test that get_token_display_pieces returns empty list when no usage."""
        mock_agent = MagicMock()

        # No cumulative_token_usage set
        result = self.token_manager.get_token_display_pieces(
            mock_agent, current_answer_token=0, use_nerd_font=False
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
