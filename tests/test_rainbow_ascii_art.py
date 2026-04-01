import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from linhai.tui.components import RainbowAsciiArt


class TestRainbowAsciiArt(unittest.TestCase):
    """Test RainbowAsciiArt width adaptation functionality."""

    def setUp(self):
        self.standard_art = r"""
  _   _      _ _       
 | | | | ___| | | ___  
 | |_| |/ _ \ | |/ _ \ 
 |  _  |  __/ | | (_) |
 |_| |_|\___|_|_|\___/ 
"""
        self.small_art = """
 _   _ _ _ 
| | | | | |
| |_| | | |
|  _  |_|_|
|_| |_(_|_)
"""

    def test_init_with_small_art(self):
        """Test initialization with small_ascii_art."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        self.assertEqual(widget.ascii_art, self.standard_art)
        self.assertEqual(widget.small_ascii_art, self.small_art)

    def test_init_with_same_art(self):
        """Test initialization with small_ascii_art same as ascii_art."""
        widget = RainbowAsciiArt(self.standard_art, self.standard_art, lambda: 0.05)
        self.assertEqual(widget.ascii_art, self.standard_art)
        self.assertEqual(widget.small_ascii_art, self.standard_art)

    def test_get_appropriate_art_wide_terminal(self):
        """Test _get_appropriate_art with wide terminal."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        # 使用PropertyMock模拟size属性，使其返回一个具有width=80的Mock对象
        mock_size = MagicMock()
        mock_size.width = 80
        with patch.object(
            RainbowAsciiArt, "size", new_callable=PropertyMock, return_value=mock_size
        ):
            art = widget._get_appropriate_art()
            # 标准艺术的最大行长度小于80，应返回标准艺术
            self.assertEqual(art, self.standard_art)

    def test_get_appropriate_art_narrow_terminal(self):
        """Test _get_appropriate_art with narrow terminal."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        # 使用PropertyMock模拟size属性，使其返回一个具有width=20的Mock对象
        mock_size = MagicMock()
        mock_size.width = 20
        with patch.object(
            RainbowAsciiArt, "size", new_callable=PropertyMock, return_value=mock_size
        ):
            art = widget._get_appropriate_art()
            # 宽度不足，应返回小型艺术
            self.assertEqual(art, self.small_art)

    def test_get_appropriate_art_no_width(self):
        """Test _get_appropriate_art when size.width is 0."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        # 使用PropertyMock模拟size属性，使其返回一个具有width=0的Mock对象
        mock_size = MagicMock()
        mock_size.width = 0
        with patch.object(
            RainbowAsciiArt, "size", new_callable=PropertyMock, return_value=mock_size
        ):
            art = widget._get_appropriate_art()
            # 宽度为0时，应返回标准艺术作为回退
            self.assertEqual(art, self.standard_art)

    def test_get_appropriate_art_same_art(self):
        """Test _get_appropriate_art when small_ascii_art is same as ascii_art."""
        widget = RainbowAsciiArt(self.standard_art, self.standard_art, lambda: 0.05)
        # 使用PropertyMock模拟size属性，使其返回一个具有width=20的Mock对象
        mock_size = MagicMock()
        mock_size.width = 20
        with patch.object(
            RainbowAsciiArt, "size", new_callable=PropertyMock, return_value=mock_size
        ):
            art = widget._get_appropriate_art()
            # small_ascii_art与ascii_art相同，应返回标准艺术
            self.assertEqual(art, self.standard_art)

    def test_render_uses_appropriate_art(self):
        """Test that _render_ascii_art uses _get_appropriate_art."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        # 模拟_get_appropriate_art方法返回小型艺术
        with patch.object(
            widget, "_get_appropriate_art", return_value=self.small_art
        ) as mock_get:
            text = widget._render_ascii_art()
            # 确保调用了_get_appropriate_art方法
            mock_get.assert_called_once()
            # 确保渲染不为空
            self.assertIsNotNone(text)
            art = widget._get_appropriate_art()
            # 宽度为0时，应返回标准艺术作为回退
            self.assertEqual(art, self.standard_art)

    def test_get_appropriate_art_same_art(self):
        """Test _get_appropriate_art when small_ascii_art is same as ascii_art."""
        widget = RainbowAsciiArt(self.standard_art, self.standard_art, lambda: 0.05)
        # 使用PropertyMock模拟size属性，使其返回一个具有width=20的Mock对象
        mock_size = MagicMock()
        mock_size.width = 20
        with patch.object(
            RainbowAsciiArt, "size", new_callable=PropertyMock, return_value=mock_size
        ):
            art = widget._get_appropriate_art()
            # small_ascii_art与ascii_art相同，应返回标准艺术
            self.assertEqual(art, self.standard_art)

    def test_render_uses_appropriate_art(self):
        """Test that _render_ascii_art uses _get_appropriate_art."""
        widget = RainbowAsciiArt(self.standard_art, self.small_art, lambda: 0.05)
        # 模拟_get_appropriate_art方法返回小型艺术
        with patch.object(
            widget, "_get_appropriate_art", return_value=self.small_art
        ) as mock_get:
            text = widget._render_ascii_art()
            # 确保调用了_get_appropriate_art方法
            mock_get.assert_called_once()
            # 确保渲染不为空
            self.assertIsNotNone(text)


if __name__ == "__main__":
    unittest.main()
