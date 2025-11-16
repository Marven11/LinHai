"""测试toolcall解析错误处理"""

import unittest
from linhai.cli.components import ToolCallWidget


class TestToolCallErrorHandling(unittest.TestCase):
    """测试toolcall解析错误处理"""

    def test_invalid_json_display_original(self):
        """测试无效JSON时显示原始内容"""
        # 创建无效的JSON字符串
        invalid_json = '{"name": "test", "args": {missing_quote: "value"}'
        
        # 创建ToolCallWidget实例，传入空字符串
        widget = ToolCallWidget("")
        # 通过feed_string喂入无效JSON来触发错误
        widget.feed_string(invalid_json)
        
        # 触发显示更新
        widget.update_display()
        
        # 验证错误状态已设置
        self.assertTrue(widget.has_error)
        # 验证原始JSON被保存
        self.assertEqual(widget.json_str, invalid_json)

    def test_valid_json_no_error(self):
        """测试有效JSON时正常解析"""
        # 创建有效的JSON字符串
        valid_json = '{"name": "test_tool", "arguments": {"param": "value"}}'
        
        # 创建ToolCallWidget实例
        widget = ToolCallWidget(valid_json)
        
        # 模拟解析过程
        widget.feed_string(valid_json)
        
        # 触发显示更新
        widget.update_display()
        
        # 验证没有错误
        self.assertFalse(widget.has_error)


if __name__ == "__main__":
    unittest.main()