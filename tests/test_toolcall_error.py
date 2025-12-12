"""测试toolcall解析错误处理"""

import unittest
from linhai.cli.components import ToolCallWidget


class TestToolCallErrorHandling(unittest.TestCase):
    """测试toolcall解析错误处理"""

    def test_invalid_json_display_original(self):
        """测试无效JSON时显示原始内容"""
        invalid_json = '{"name": "test", "args": {missing_quote: "value"}'

        widget = ToolCallWidget("")
        widget.feed_string(invalid_json)

        widget.update_display()

        self.assertTrue(widget.has_error)
        self.assertEqual(widget.json_str, invalid_json)

    def test_valid_json_no_error(self):
        """测试有效JSON时正常解析"""
        valid_json = '{"name": "test_tool", "arguments": {"param": "value"}}'

        widget = ToolCallWidget(valid_json)

        widget.feed_string(valid_json)

        widget.update_display()

        self.assertFalse(widget.has_error)


if __name__ == "__main__":
    unittest.main()
