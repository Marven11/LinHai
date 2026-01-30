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
        )
        self.assertEqual(msg.image_bytes, image_bytes)
        self.assertEqual(msg.mime_type, "image/jpeg")
        self.assertEqual(msg.filename, "test.jpg")

    def test_to_base64(self):
        """Test converting to base64."""
        image_bytes = b"test_data"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
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
        )
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["mime_type"], "image/webp")
        self.assertEqual(data["filename"], "test.webp")
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
        )
        json_str = original.to_json()

        mock_group_chat = MagicMock()
        restored = ImageMessage.from_json(json_str, mock_group_chat)

        self.assertEqual(restored.image_bytes, image_bytes)
        self.assertEqual(restored.mime_type, "image/bmp")
        self.assertEqual(restored.filename, "test.bmp")


class TestLoadImage(TestCase):
    """Test load_image function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()

    def test_load_image_success(self):
        """Test loading an existing image file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake_png_data")
            temp_path = f.name

        try:
            result = load_image(temp_path, self.mock_group_chat)
            self.assertIsInstance(result, ImageMessage)
            self.assertEqual(result.image_bytes, b"fake_png_data")
            self.assertEqual(result.mime_type, "image/png")
            self.assertEqual(result.filename, Path(temp_path).name)
        finally:
            Path(temp_path).unlink()

    def test_load_image_not_found(self):
        """Test loading a non-existent file raises error."""
        with self.assertRaises(FileNotFoundError):
            load_image("/nonexistent/path/image.png", self.mock_group_chat)

    def test_load_image_different_mime_types(self):
        """Test loading files with different extensions."""
        test_cases = [
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/gif"),
            (".webp", "image/webp"),
            (".bmp", "image/bmp"),
        ]

        for ext, expected_mime in test_cases:
            with self.subTest(ext=ext):
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    f.write(b"fake_data")
                    temp_path = f.name

                try:
                    result = load_image(temp_path, self.mock_group_chat)
                    self.assertEqual(result.mime_type, expected_mime)
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
        self.mock_group_chat.get_members.return_value = self.mock_agent

    def test_to_llm_message_with_supported_llm(self):
        """Test conversion when LLM supports images."""
        image_bytes = b"fake_image"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
        )

        result = msg.to_llm_message()

        self.assertEqual(result["role"], "user")
        self.assertIsInstance(result["content"], list)
        self.assertEqual(result["content"][0]["type"], "image_url")

    def test_to_llm_message_with_unsupported_llm(self):
        """Test conversion when LLM does not support images."""
        # 设置LLM不支持图片
        self.mock_llm.support_image = MagicMock(return_value=False)

        image_bytes = b"fake_image"
        msg = ImageMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            filename=None,
            group_chat=self.mock_group_chat,
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
