"""测试自动补全功能"""

import unittest
from unittest.mock import Mock
from linhai.cli.autocomplete import AutocompleteInput


class TestAutocompleteInput(unittest.TestCase):
    """测试AutocompleteInput类"""

    def setUp(self):
        """设置测试环境"""
        self.input_widget = AutocompleteInput()
        # 使用动态补全提供器
        self.input_widget.set_dynamic_completion_providers(
            lambda: ["user", "assistant", "agent", "subagent", "tool"],
            lambda: ["help", "exit", "clear", "history", "config"]
        )

    def test_get_suggestions_empty_input(self):
        """测试空输入时的补全"""
        target_state = Mock()
        target_state.value = ""
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(suggestions, [])

    def test_get_suggestions_at_prefix(self):
        """测试@前缀的补全"""
        target_state = Mock()
        target_state.value = "@us"
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].value, "user")

    def test_get_suggestions_slash_prefix(self):
        """测试/前缀的补全"""
        target_state = Mock()
        target_state.value = "/he"
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].value, "help")

    def test_get_suggestions_no_prefix(self):
        """测试无前缀的补全"""
        target_state = Mock()
        target_state.value = "test"
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(suggestions, [])

    def test_get_suggestions_case_insensitive(self):
        """测试大小写不敏感的补全"""
        target_state = Mock()
        target_state.value = "@US"
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].value, "user")

    def test_get_suggestions_limit(self):
        """测试补全数量限制"""
        # 使用动态提供器返回更多项
        self.input_widget.set_dynamic_completion_providers(
            lambda: [f"user{i}" for i in range(15)],
            lambda: [f"command{i}" for i in range(15)]
        )
        
        target_state = Mock()
        target_state.value = "@user"
        suggestions = self.input_widget.get_suggestions(target_state)
        self.assertEqual(len(suggestions), 10)  # 应该限制为10个


if __name__ == "__main__":
    unittest.main()