"""Unit tests for utils module."""

import unittest
import re
from linhai.utils import generate_id


class TestUtils(unittest.TestCase):
    """Test cases for utils functions."""

    def test_generate_id_format(self):
        """Test generate_id function output format."""
        # 测试terminal前缀
        terminal_id = generate_id("terminal")
        self.assertTrue(terminal_id.startswith("terminal_"))
        
        # 测试largemessage前缀
        large_message_id = generate_id("largemessage")
        self.assertTrue(large_message_id.startswith("largemessage_"))
        
        # 测试自定义前缀
        custom_id = generate_id("custom")
        self.assertTrue(custom_id.startswith("custom_"))
    
    def test_generate_id_length(self):
        """Test generate_id function output length."""
        terminal_id = generate_id("terminal")
        # format: prefix_ + 12 hex chars
        expected_length = len("terminal_") + 12
        self.assertEqual(len(terminal_id), expected_length)
        
        large_message_id = generate_id("largemessage")
        expected_length = len("largemessage_") + 12
        self.assertEqual(len(large_message_id), expected_length)
    
    def test_generate_id_hex_format(self):
        """Test generate_id function hex part format."""
        terminal_id = generate_id("terminal")
        # 提取hex部分 (在最后一个下划线之后)
        parts = terminal_id.split("_")
        self.assertEqual(len(parts), 2)
        hex_part = parts[1]
        
        # 检查是否为12位十六进制
        self.assertEqual(len(hex_part), 12)
        self.assertTrue(re.match(r"^[0-9a-f]{12}$", hex_part))
    
    def test_generate_id_uniqueness(self):
        """Test generate_id function produces unique IDs."""
        # 生成多个ID确保唯一性
        ids = set()
        for _ in range(100):
            terminal_id = generate_id("terminal")
            large_message_id = generate_id("largemessage")
            ids.add(terminal_id)
            ids.add(large_message_id)
        
        # 应该有200个唯一ID
        self.assertEqual(len(ids), 200)


if __name__ == "__main__":
    unittest.main()
