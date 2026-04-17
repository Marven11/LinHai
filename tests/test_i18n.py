import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
