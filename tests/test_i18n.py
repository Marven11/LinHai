import unittest
from unittest.mock import patch, Mock

from linhai.utils.i18n import t


class TestI18n(unittest.TestCase):
    def test_missing_en_raises_value_error(self):
        with self.assertRaises(ValueError):
            t({"zh_CN": "测试"})

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_match_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"zh_CN": "平均长度: xxx token", "en": "Average length: xxx token"})
        self.assertEqual(result, "平均长度: xxx token")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_fallback_to_en_for_unknown_locale(self, mock_getlocale):
        mock_getlocale.return_value = ("ja_JP", "UTF-8")
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_none_locale_returns_en(self, mock_getlocale):
        mock_getlocale.return_value = (None, None)
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_only_en_key(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_en_us_falls_to_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    def test_t_function_in_app_py_context(self):
        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("zh_CN", "UTF-8")
            result = t(
                {
                    "zh_CN": "Enter发送，Shift+Enter换行（如果终端支持）",
                    "en": "Enter to send, Shift+Enter for newline (if terminal supports)",
                }
            )
            self.assertEqual(result, "Enter发送，Shift+Enter换行（如果终端支持）")

        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("en_US", "UTF-8")
            result = t(
                {
                    "zh_CN": "Enter发送，Shift+Enter换行（如果终端支持）",
                    "en": "Enter to send, Shift+Enter for newline (if terminal supports)",
                }
            )
            self.assertEqual(
                result, "Enter to send, Shift+Enter for newline (if terminal supports)"
            )

    def test_suicide_tool_descriptions(self):
        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("zh_CN", "UTF-8")
            result = t(
                {"zh_CN": "杀死自己并退出APP", "en": "Kill self and exit the app"}
            )
            self.assertEqual(result, "杀死自己并退出APP")

        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("en_US", "UTF-8")
            result = t(
                {
                    "zh_CN": "退出代码，0表示成功，非0表示错误",
                    "en": "Exit code, 0 for success, non-zero for error",
                }
            )
            self.assertEqual(result, "Exit code, 0 for success, non-zero for error")

    def test_app_py_imports_work(self):
        from linhai.tui.app import TUIApp
        from linhai.utils.i18n import t


class TestPromptI18n(unittest.TestCase):
    def test_all_prompt_constants_are_strings(self):
        from linhai import prompt

        constants = [
            prompt.OVERVIEW,
            prompt.INTRODUCTION_SOUL,
            prompt.INTRODUCTION_TOOL_USE,
            prompt.INTRODUCTION_WAITING_USER,
            prompt.INTRODUCTION_GLOBAL_PROMPT,
            prompt.INTRODUCTION_CONTEXT_MANAGEMENT,
            prompt.INTRODUCTION_SECRET_SYSTEM,
            prompt.INTRODUCTION_MACHINE_CONTROL_BASIC,
            prompt.INTRODUCTION_MACHINE_CONTROL,
            prompt.INTRODUCTION_PLANNING_MODE,
            prompt.RULES_TOOL_USE,
            prompt.RULES_CODING_STYLE,
            prompt.RULES_USER_ITERATION,
            prompt.EXAMPLES_TOOL_CALL,
            prompt.EXAMPLES_SECRET_USAGE,
            prompt.EXAMPLE_MULTIHOP_MACHINES,
            prompt.EXAMPLES_PLANNING_MODE,
            prompt.AGENTS_MD,
            prompt.BOOTSTRAP_MD,
            prompt.IDENTITY_MD,
            prompt.SOUL_MD,
            prompt.USER_MD,
            prompt.REMINDER_MD,
            prompt.COMPRESS_RANGE_PROMPT,
            prompt.PLANNING_MODE_PROMPT,
        ]
        for const in constants:
            self.assertIsInstance(const, str)
            self.assertTrue(len(const) > 0)

    def test_format_placeholders_in_secret_system(self):
        from linhai.prompt import INTRODUCTION_SECRET_SYSTEM

        self.assertIn("{secrets_list}", INTRODUCTION_SECRET_SYSTEM)

    def test_format_placeholders_in_planning_mode(self):
        from linhai.prompt import INTRODUCTION_PLANNING_MODE

        self.assertIn("{status_file}", INTRODUCTION_PLANNING_MODE)
        self.assertIn("{todolist_file}", INTRODUCTION_PLANNING_MODE)
        self.assertIn("{design_file}", INTRODUCTION_PLANNING_MODE)

    def test_format_placeholders_in_planning_mode_prompt(self):
        from linhai.prompt import PLANNING_MODE_PROMPT

        self.assertIn("{status_file}", PLANNING_MODE_PROMPT)
        self.assertIn("{todolist_file}", PLANNING_MODE_PROMPT)
        self.assertIn("{design_file}", PLANNING_MODE_PROMPT)

    def test_format_placeholders_in_compress_range(self):
        from linhai.prompt import COMPRESS_RANGE_PROMPT

        self.assertIn("{|SUMMERIZATION|}", COMPRESS_RANGE_PROMPT)
        self.assertIn("{|SUGGESTED_MESSAGE_COUNT|}", COMPRESS_RANGE_PROMPT)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_prompt_overview_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"zh_CN": "你是林海漫游", "en": "You are LinHai Wanderer"})
        self.assertIn("林海漫游", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_prompt_overview_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t({"zh_CN": "你是林海漫游", "en": "You are LinHai Wanderer"})
        self.assertIn("LinHai Wanderer", result)


if __name__ == "__main__":
    unittest.main()
