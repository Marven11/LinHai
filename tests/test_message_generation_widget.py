"""测试MessageGenerationWidget组件"""

import unittest
from unittest.mock import Mock
from linhai.cli.components import (
    MessageGenerationWidget,
    MessageWidget,
    RuntimeMessageWidget,
)


class TestMessageGenerationWidget(unittest.TestCase):
    """测试MessageGenerationWidget组件"""

    def setUp(self):
        """设置测试环境"""
        self.widget = MessageGenerationWidget()
        # 模拟mount方法
        self.widget.mount = Mock()

    def test_set_message_widget(self):
        """测试设置MessageWidget"""
        mock_widget = Mock(spec=MessageWidget)
        self.widget.set_message_widget(mock_widget)
        self.widget.mount.assert_called_once_with(mock_widget)

    def test_add_runtime_message(self):
        """测试添加RuntimeMessageWidget"""
        mock_widget = Mock(spec=RuntimeMessageWidget)
        self.widget.add_runtime_message(mock_widget)
        self.widget.mount.assert_called_once_with(mock_widget)


if __name__ == "__main__":
    unittest.main()