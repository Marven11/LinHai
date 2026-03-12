"""Tests for multimodal functionality."""

import base64
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from linhai.multimodal import ImageMessage, load_image


class TestImageMessage(TestCase):
    """Test ImageMessage class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()

    def test_init(self):
        """Test ImageMessage initialization."""
        image_bytes = b"fake_image_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            filename="test.jpg",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        self.assertEqual(msg.image_bytes, image_bytes)
        self.assertEqual(msg.mime_type, "image/jpeg")
        self.assertEqual(msg.filename, "test.jpg")
        self.assertEqual(msg.quality, "raw")

    def test_to_base64(self):
        """Test converting to base64."""
        image_bytes = b"test_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        expected = base64.b64encode(image_bytes).decode("utf-8")
        self.assertEqual(msg.to_data_url().split(",")[1], expected)

    def test_to_data_url(self):
        """Test generating data URL."""
        image_bytes = b"test_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        expected = f"data:image/png;base64,{base64_data}"
        self.assertEqual(msg.to_data_url(), expected)

    def test_save_to_temp_file(self):
        """Test saving to temporary file."""
        image_bytes = b"fake_image_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename="test.png",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        temp_path = msg.save_to_temp_file()
        self.assertTrue(temp_path.exists())
        with open(temp_path, "rb") as f:
            self.assertEqual(f.read(), image_bytes)

    def test_repr(self):
        """Test string representation."""
        image_bytes = b"test"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/gif",
            filename=None,
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        repr_str = repr(msg)
        self.assertIn("ImageMessage", repr_str)
        self.assertIn("4 bytes", repr_str)

    def test_to_json(self):
        """Test serialization to JSON."""
        image_bytes = b"test_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/webp",
            filename="test.webp",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["mime_type"], "image/webp")
        self.assertEqual(data["filename"], "test.webp")
        self.assertEqual(data["width"], 100)
        self.assertEqual(data["height"], 100)
        decoded = base64.b64decode(data["image_bytes"])
        self.assertEqual(decoded, image_bytes)

    def test_from_json(self):
        """Test deserialization from JSON."""
        image_bytes = b"test_data"
        original = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/bmp",
            filename="test.bmp",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        json_str = original.to_json()

        mock_group_chat = MagicMock()
        restored = ImageMessage.from_json(json_str, mock_group_chat)

        self.assertEqual(restored.image_bytes, image_bytes)
        self.assertEqual(restored.mime_type, "image/bmp")
        self.assertEqual(restored.filename, "test.bmp")
        self.assertEqual(restored.width, 100)
        self.assertEqual(restored.height, 100)


class TestLoadImage(TestCase):
    """Test load_image function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()

    def test_load_image_success(self):
        """Test loading an existing image file."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (100, 100), color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        png_data = buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png_data)
            temp_path = f.name

        try:
            result = load_image(temp_path, self.mock_group_chat, quality="raw")
            self.assertIsInstance(result, ImageMessage)
            self.assertEqual(result.mime_type, "image/png")
            self.assertEqual(result.filename, Path(temp_path).name)
        finally:
            Path(temp_path).unlink()

    def test_load_image_parameter_name(self):
        """Test that load_image uses correct parameter name (image_filepath)."""
        import inspect
        import linhai.multimodal as multimodal_module

        func_doc = multimodal_module.load_image.__doc__ or ""
        self.assertIn("image_filepath", func_doc)

    def test_load_image_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_image(
                "/nonexistent/path/image.png", self.mock_group_chat, quality="raw"
            )

    def test_load_image_different_mime_types(self):
        from PIL import Image
        from io import BytesIO

        test_cases = [
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/png"),  # GIF转换为PNG因为模式转换
            (".webp", "image/png"),  # WEBP转换为PNG因为llama.cpp不支持
            (".bmp", "image/bmp"),
        ]

        for ext, expected_mime in test_cases:
            with self.subTest(ext=ext):
                img = Image.new("RGB", (100, 100), color="red")
                buffer = BytesIO()
                format_map = {
                    ".jpg": "JPEG",
                    ".jpeg": "JPEG",
                    ".gif": "GIF",
                    ".webp": "WEBP",
                    ".bmp": "BMP",
                }
                img.save(buffer, format=format_map[ext])
                image_data = buffer.getvalue()

                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    f.write(image_data)
                    temp_path = f.name

                try:
                    result = load_image(temp_path, self.mock_group_chat, quality="raw")
                    self.assertEqual(result.mime_type, expected_mime)
                finally:
                    Path(temp_path).unlink()

    def test_load_image_quality_parameter(self):
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (100, 100), color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        png_data = buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png_data)
            temp_path = f.name

        try:
            result = load_image(temp_path, self.mock_group_chat, quality="raw")
            self.assertEqual(result.quality, "raw")

            result2 = load_image(temp_path, self.mock_group_chat, quality="compressed")
            self.assertEqual(result2.quality, "compressed")
        finally:
            Path(temp_path).unlink()


class TestImageMessageToLlmMessage(TestCase):
    """Test ImageMessage.to_llm_message method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()
        self.mock_agent = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_llm.support_image = MagicMock(return_value=True)
        self.mock_agent.get_current_model.return_value = self.mock_llm
        self.mock_group_chat.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.mock_agent
        )

    def test_to_llm_message_with_supported_llm(self):
        """Test conversion when LLM supports images."""
        image_bytes = b"fake_image"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )

        result = msg.to_llm_message()

        self.assertEqual(result["role"], "user")
        self.assertIsInstance(result["content"], list)
        self.assertEqual(result["content"][0]["type"], "image_url")

    def test_to_llm_message_with_unsupported_llm(self):
        """Test conversion when LLM does not support images."""
        self.mock_llm.support_image = MagicMock(return_value=False)

        image_bytes = b"fake_image"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )

        with patch.object(msg, "save_to_temp_file") as mock_save:
            mock_save.return_value = Path("/tmp/test_image.png")
            result = msg.to_llm_message()

        self.assertEqual(result["role"], "user")
        self.assertIsInstance(result["content"], str)
        self.assertIn("不支持查看图片", result["content"])
        self.assertIn("/tmp/test_image.png", result["content"])


if __name__ == "__main__":
    import unittest

    unittest.main()
