"""Tests for TelegramStickerMessage functionality."""

import base64
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from linhai.telegram import TelegramStickerMessage, load_sticker


class TestTelegramStickerMessage(TestCase):
    """Test TelegramStickerMessage class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()

    def test_init(self):
        """Test TelegramStickerMessage initialization."""
        image_bytes = b"fake_image_data"
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        self.assertEqual(msg.image_bytes, image_bytes)
        self.assertEqual(msg.mime_type, "image/jpeg")
        self.assertEqual(msg.quality, "raw")
        self.assertEqual(msg.width, 100)
        self.assertEqual(msg.height, 100)

    def test_to_data_url(self):
        """Test generating data URL."""
        image_bytes = b"test_data"
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
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
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        temp_path = msg.save_to_temp_file()
        self.assertTrue(temp_path.exists())
        self.assertTrue(temp_path.suffix == ".png")
        with open(temp_path, "rb") as f:
            self.assertEqual(f.read(), image_bytes)
        temp_path.unlink()

    def test_repr(self):
        """Test string representation."""
        image_bytes = b"test"
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/gif",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        repr_str = repr(msg)
        self.assertIn("TelegramStickerMessage", repr_str)
        self.assertIn("4 bytes", repr_str)

    def test_to_json(self):
        """Test serialization to JSON."""
        image_bytes = b"test_data"
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/webp",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        json_str = msg.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["mime_type"], "image/webp")
        self.assertEqual(data["width"], 100)
        self.assertEqual(data["height"], 100)
        decoded = base64.b64decode(data["image_bytes"])
        self.assertEqual(decoded, image_bytes)

    def test_from_json(self):
        """Test deserialization from JSON."""
        image_bytes = b"test_data"
        original = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/bmp",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )
        json_str = original.to_json()

        mock_group_chat = MagicMock()
        restored = TelegramStickerMessage.from_json(json_str, mock_group_chat)

        self.assertEqual(restored.image_bytes, image_bytes)
        self.assertEqual(restored.mime_type, "image/bmp")
        self.assertEqual(restored.width, 100)
        self.assertEqual(restored.height, 100)


class TestTelegramStickerMessageToLlmMessage(TestCase):
    """Test TelegramStickerMessage.to_llm_message method."""

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
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
            group_chat=self.mock_group_chat,
            width=100,
            height=100,
        )

        result = msg.to_llm_message()

        self.assertEqual(result["role"], "user")
        self.assertIsInstance(result["content"], list)
        self.assertEqual(len(result["content"]), 2)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn(
            "<<telegram>><<message>>用户向你发送了一张表情包<<message>><<telegram>>",
            result["content"][0]["text"],
        )
        self.assertEqual(result["content"][1]["type"], "image_url")

    def test_to_llm_message_with_unsupported_llm(self):
        """Test conversion when LLM does not support images."""
        self.mock_llm.support_image = MagicMock(return_value=False)

        image_bytes = b"fake_image"
        msg = TelegramStickerMessage(
            image_bytes=image_bytes,
            mime_type="image/png",
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
        self.assertIn(
            "<<telegram>><<message>>用户向你发送了一张表情包<<message>><<telegram>>",
            result["content"],
        )


class TestLoadSticker(TestCase):
    """Test load_sticker function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()

    def test_load_sticker_success(self):
        """Test loading a valid sticker image."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (200, 100), color="blue")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        sticker_data = buffer.getvalue()

        result = load_sticker(sticker_data, self.mock_group_chat)
        self.assertIsInstance(result, TelegramStickerMessage)
        self.assertEqual(result.mime_type, "image/jpeg")
        self.assertEqual(result.quality, "compressed")
        self.assertLessEqual(result.width, 128)
        self.assertLessEqual(result.height, 128)

    def test_load_sticker_square_image(self):
        """Test loading a square sticker image."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (256, 256), color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        sticker_data = buffer.getvalue()

        result = load_sticker(sticker_data, self.mock_group_chat)
        self.assertEqual(result.width, 128)
        self.assertEqual(result.height, 128)

    def test_load_sticker_landscape_image(self):
        """Test loading a landscape sticker image."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (300, 100), color="green")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        sticker_data = buffer.getvalue()

        result = load_sticker(sticker_data, self.mock_group_chat)
        self.assertLessEqual(result.width, 128)
        self.assertLessEqual(result.height, 128)
        self.assertAlmostEqual(
            result.width / result.height,
            3,
            delta=0.05,
            msg="Aspect ratio should be preserved",
        )

    def test_load_sticker_portrait_image(self):
        """Test loading a portrait sticker image."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (100, 300), color="yellow")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        sticker_data = buffer.getvalue()

        result = load_sticker(sticker_data, self.mock_group_chat)
        self.assertLessEqual(result.width, 128)
        self.assertLessEqual(result.height, 128)
        self.assertAlmostEqual(
            result.height / result.width,
            3,
            delta=0.05,
            msg="Aspect ratio should be preserved",
        )

    def test_load_sticker_rgba_image(self):
        """Test loading an RGBA sticker image."""
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        sticker_data = buffer.getvalue()

        result = load_sticker(sticker_data, self.mock_group_chat)
        self.assertEqual(result.mime_type, "image/jpeg")
        self.assertEqual(result.quality, "compressed")


if __name__ == "__main__":
    import unittest

    unittest.main()
