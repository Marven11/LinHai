"""Telegram消息模块，包含TelegramMessage和TelegramStickerMessage类。"""

from typing import TYPE_CHECKING
import json
import base64
import tempfile
from pathlib import Path
from PIL import Image
from io import BytesIO
from typing import Literal

import math

from linhai.base import EstimateToken, LanguageModelMessage, Message, register_message

if TYPE_CHECKING:
    from linhai.registry import Registry


@register_message
class TelegramMessage(Message):
    """Telegram消息，用于表示来自telegram的消息。"""

    def __init__(self, chat_id: str, content: str, message_id: int = 0):
        self.chat_id = chat_id
        self.content = content
        self.message_id = message_id

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        return f"<<telegram>>\nchat_id: {self.chat_id}\nmessage_id: {self.message_id}\n{self.content}\n<<telegram>>"

    def to_json(self) -> str:
        data = {
            "chat_id": self.chat_id,
            "content": self.content,
            "message_id": self.message_id,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry):
        data = json.loads(json_str)
        return cls(
            chat_id=data["chat_id"],
            content=data["content"],
            message_id=data["message_id"],
        )

    def __eq__(self, other) -> bool:
        """比较两个TelegramMessage是否相同。"""
        if not isinstance(other, TelegramMessage):
            return NotImplemented
        return (
            self.chat_id == other.chat_id
            and self.content == other.content
            and self.message_id == other.message_id
        )

    def __hash__(self) -> int:
        """哈希支持，用于set比较。"""
        return hash((self.chat_id, self.content, self.message_id))

    def __str__(self) -> str:
        return f"TelegramMessage(chat_id={self.chat_id}, message_id={self.message_id})"


@register_message
class TelegramStickerMessage(Message):
    """Telegram表情包消息类，在内存中保存图片bytes数据。"""

    def __init__(
        self,
        image_bytes: bytes,
        mime_type: str,
        registry: "Registry",
        width: int,
        height: int,
        quality: Literal["compressed", "raw"] = "raw",
    ):
        """初始化表情包消息。

        Args:
            image_bytes: 图片的二进制数据
            mime_type: 图片的MIME类型
            registry: Registry实例（用于动态获取LLM支持状态）
            width: 图片宽度
            height: 图片高度
            quality: 图片质量，"compressed"表示压缩图像，"raw"表示原始图像（默认）
        """
        self.image_bytes = image_bytes
        self.mime_type = mime_type
        self.registry = registry
        self.quality = quality
        self.width = width
        self.height = height

    def to_data_url(self) -> str:
        """生成data URL格式的图片URL。"""
        base64_data = base64.b64encode(self.image_bytes).decode("utf-8")
        return f"data:{self.mime_type};base64,{base64_data}"

    def save_to_temp_file(self) -> Path:
        """将图片保存到临时文件，返回文件路径。"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(self.image_bytes)
            return Path(f.name)

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。

        支持两个block的content：
        1. 系统消息文本："<<telegram>><<message>>用户向你发送了一张表情包<<message>><<telegram>>"
        2. 表情包图片本身

        如果不支持图像，则保存到临时文件并返回文本消息。

        Returns:
            LanguageModelMessage: 转换后的消息
        """
        from linhai.agent.main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm = agent.get_current_model()
        if llm.support_image():
            return {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "<<telegram>><<message>>用户向你发送了一张表情包<<message>><<telegram>>",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": self.to_data_url()},
                    },
                ],
            }
        else:
            temp_path = self.save_to_temp_file()
            estimated_tokens = self.estimated_tokens()
            return {
                "role": "user",
                "content": f"<<telegram>><<message>>用户向你发送了一张表情包<<message>><<telegram>>\n\n你不支持查看图片，图片内容已经自动转储到以下路径，用其他适当的方式间接查看这张图片（估算token用量: {estimated_tokens}）：\n{temp_path}",
            }

    def estimated_tokens(self) -> int:
        tokens_h = math.ceil(self.height / 32)
        tokens_w = math.ceil(self.width / 32)
        return tokens_h * tokens_w

    def get_content(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"TelegramStickerMessage(size={len(self.image_bytes)} bytes, mime_type={self.mime_type}, quality={self.quality}, width={self.width}, height={self.height})"

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {
            "image_bytes": base64.b64encode(self.image_bytes).decode("utf-8"),
            "mime_type": self.mime_type,
            "quality": self.quality,
            "width": self.width,
            "height": self.height,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: "Registry") -> "TelegramStickerMessage":
        """从JSON字符串创建TelegramStickerMessage实例。"""
        data = json.loads(json_str)
        image_bytes = base64.b64decode(data["image_bytes"])
        return cls(
            image_bytes=image_bytes,
            mime_type=data.get("mime_type", "image/png"),
            registry=registry,
            quality=data.get("quality", "raw"),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )


def load_sticker(sticker_data: bytes, registry: "Registry") -> TelegramStickerMessage:
    """加载表情包数据并返回TelegramStickerMessage。

    Args:
        sticker_data: 表情包的二进制数据
        registry: Registry实例（用于动态获取LLM支持状态）

    Returns:
        TelegramStickerMessage: 包含表情包数据的消息对象

    Raises:
        ValueError: 图片数据损坏或格式不支持
    """
    buffer = BytesIO(sticker_data)

    with Image.open(buffer) as img:
        img.verify()

    buffer.seek(0)
    with Image.open(buffer) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        width, height = img.size

        img.thumbnail((128, 128), Image.Resampling.LANCZOS)
        final_width, final_height = img.size

        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=85, optimize=True)
        image_bytes = output_buffer.getvalue()
        mime_type = "image/jpeg"

    return TelegramStickerMessage(
        image_bytes=image_bytes,
        mime_type=mime_type,
        registry=registry,
        quality="compressed",
        width=final_width,
        height=final_height,
    )
