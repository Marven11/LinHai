"""Unit tests for the input parser module."""

import unittest
from linhai.input_parser import parse_user_input


class TestInputParser(unittest.TestCase):
    """Test cases for the input parser."""

    def test_parse_empty_input(self):
        """Test parsing empty input."""
        result = parse_user_input("")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, [])

    def test_parse_command_only(self):
        """Test parsing command only."""
        result = parse_user_input("/help")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, "help")
        self.assertEqual(result.mentioned, [])

    def test_parse_mentioned_only(self):
        """Test parsing mentioned names only."""
        result = parse_user_input("Hello @alice and @bob")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, ["alice", "bob"])

    def test_parse_command_and_mentioned(self):
        """Test parsing both command and mentioned names."""
        result = parse_user_input("/help @alice @bob")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, "help")
        self.assertEqual(result.mentioned, ["alice", "bob"])

    def test_parse_mentioned_with_special_chars(self):
        """Test parsing mentioned names with special characters."""
        result = parse_user_input("Hello @user-name and @user_name")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, ["user-name", "user_name"])

    def test_parse_mentioned_at_end(self):
        """Test parsing mentioned names at the end of input."""
        result = parse_user_input("Hello @user")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, ["user"])

    def test_parse_mentioned_with_punctuation(self):
        """Test parsing mentioned names followed by punctuation."""
        result = parse_user_input("Hello @user! How are you?")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, ["user"])

    def test_parse_no_mentioned_when_at_start(self):
        """Test that @ at the start of line is not treated as mention."""
        result = parse_user_input("@start should not be mentioned")
        self.assertEqual(result.switch_model, "start")
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, [])

    def test_parse_duplicate_mentioned(self):
        """Test that duplicate mentioned names are deduplicated."""
        result = parse_user_input("Hello @user @user @user")
        self.assertEqual(result.switch_model, None)
        self.assertEqual(result.command, None)
        self.assertEqual(result.mentioned, ["user"])


if __name__ == "__main__":
    unittest.main()