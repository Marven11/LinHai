import unittest
from pathlib import Path

from linhai.agent.messages.file_content import DynamicFileContentMessage
from linhai.base import Message


class TestDynamicContentReading(unittest.TestCase):
    def setUp(self):
        self.test_file = Path("test_temp_dyn_content.txt")
        self.test_file.write_text("line1\nline2\nline3")

    def tearDown(self):
        if self.test_file.exists():
            self.test_file.unlink()

    def test_reads_latest_content_on_each_call(self):
        msg = DynamicFileContentMessage(str(self.test_file), False)
        self.assertIn("line1", msg.get_content())
        self.test_file.write_text("completely_new")
        self.assertIn("completely_new", msg.get_content())
        self.assertNotIn("line1", msg.get_content())

    def test_line_numbers_format(self):
        msg = DynamicFileContentMessage(str(self.test_file), True)
        content = msg.get_content()
        self.assertIn("1: line1", content)
        self.assertIn("2: line2", content)
        self.assertIn("3: line3", content)

    def test_no_line_numbers_format(self):
        msg = DynamicFileContentMessage(str(self.test_file), False)
        content = msg.get_content()
        self.assertIn("line1", content)
        self.assertNotIn("1:", content)

    def test_file_not_found_returns_error(self):
        msg = DynamicFileContentMessage("/nonexistent/path/file.txt", False)
        content = msg.get_content()
        self.assertIn("error", content.lower())
        self.assertIn("/nonexistent/path/file.txt", content)

    def test_empty_file(self):
        self.test_file.write_text("")
        msg = DynamicFileContentMessage(str(self.test_file), True)
        content = msg.get_content()
        self.assertIn("file_content", content)

    def test_to_llm_message_is_user_role(self):
        msg = DynamicFileContentMessage(str(self.test_file), False)
        llm_msg = msg.to_llm_message()
        self.assertEqual(llm_msg["role"], "user")
        self.assertIn("line1", llm_msg["content"])

    def test_is_message_instance(self):
        msg = DynamicFileContentMessage(str(self.test_file), False)
        self.assertIsInstance(msg, Message)
