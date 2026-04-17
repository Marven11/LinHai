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


if __name__ == "__main__":
    unittest.main()
