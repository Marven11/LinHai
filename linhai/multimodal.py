"""多模态支持模块。

包含ImageMessage消息类，load_image工具，以及动态工具集管理。
"""

from __future__ import annotations
import base64
import json
import tempfile
from pathlib import Path
from typing import cast

from linhai.llm import Message
from linhai.agent.lifecycle import Lifecycle
from linhai.type_hints import LanguageModelMessage
from linhai.group_chat import GroupChat


class ImageMessage(Message):
    """图片消息类，在内存中保存图片bytes数据。"""

    def __init__(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None,
        group_chat: GroupChat,
    ):
        """初始化图片消息。

        Args:
            image_bytes: 图片的二进制数据
            mime_type: 图片的MIME类型
            filename: 原始文件名（可选，None表示未知）
            group_chat: GroupChat实例（用于动态获取LLM支持状态）
        """
        self.image_bytes = image_bytes
        self.mime_type = mime_type
        self.filename = filename
        self.group_chat = group_chat

    def to_data_url(self) -> str:
        """生成data URL格式的图片URL。"""
        base64_data = base64.b64encode(self.image_bytes).decode("utf-8")
        return f"data:{self.mime_type};base64,{base64_data}"

    def save_to_temp_file(self) -> Path:
        """将图片保存到临时文件，返回文件路径。"""
        suffix = Path(self.filename).suffix if self.filename else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(self.image_bytes)
            return Path(f.name)

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。

        动态检查当前LLM是否支持图像，如果支持则返回image_url格式，
        否则保存到临时文件并返回文本消息。

        严格按照_current_llm_supports_image的方法获取LLM支持状态：
        - 通过self.group_chat获取agent
        - 调用agent.get_current_model()获取当前llm
        - 调用llm.support_image()获取支持状态

        Returns:
            LanguageModelMessage: 转换后的消息
        """
        from linhai.agent.main import Agent
        agent = self.group_chat.get_members("agent", Agent)
        llm = agent.get_current_model()
        if llm.support_image():
            return {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": self.to_data_url()},
                    }
                ],
            }
        else:
            temp_path = self.save_to_temp_file()
            content = f"<<image>><<message>>你不支持查看图片，图片内容已经自动转储到以下路径，用其他适当的方式间接查看这张图片<<message>><<filepath>>{temp_path}<<filepath>><<image>>"
            return cast(LanguageModelMessage, {"role": "user", "content": content})

    def __repr__(self) -> str:
        return f"ImageMessage(size={len(self.image_bytes)} bytes, mime_type={self.mime_type})"

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {
            "image_bytes": base64.b64encode(self.image_bytes).decode("utf-8"),
            "mime_type": self.mime_type,
            "filename": self.filename,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: GroupChat
    ) -> "ImageMessage":
        """从JSON字符串创建ImageMessage实例。"""
        data = json.loads(json_str)
        image_bytes = base64.b64decode(data["image_bytes"])
        return cls(
            image_bytes=image_bytes,
            mime_type=data.get("mime_type", "image/png"),
            filename=data.get("filename"),
            group_chat=group_chat,
        )


def load_image(image_path: str, group_chat: GroupChat) -> ImageMessage:
    """加载图片文件并返回ImageMessage。

    Args:
        image_path: 图片文件路径
        group_chat: GroupChat实例（用于动态获取LLM支持状态）

    Returns:
        ImageMessage: 包含图片数据的消息对象

    Raises:
        FileNotFoundError: 图片文件不存在
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(path.suffix.lower(), "image/png")

    with open(path, "rb") as f:
        image_bytes = f.read()

    return ImageMessage(
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=path.name,
        group_chat=group_chat,
    )


from linhai.tool.base import ToolSet, ToolArgInfo


class MultimodalToolsetManager:
    """多模态工具集管理器，根据当前LLM配置动态调整工具集。

    设计原则：
    - 创建一个ToolSet用于存放load_image工具
    - 在初始化时添加到ToolManager
    - 根据LLM配置动态添加/移除工具，而不是整个ToolSet
    """

    def __init__(self, group_chat: GroupChat):
        """初始化多模态工具集管理器。"""
        self.group_chat = group_chat
        self.group_chat.register_member("multimodal_toolset_manager", self)

        # 创建一个ToolSet，用于存放load_image工具
        self._toolset = ToolSet()

        # 添加到ToolManager
        from linhai.tool.main import ToolManager
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        tool_manager.add_toolset(self._toolset)

    def register_lifecycle(self, lifecycle: Lifecycle) -> None:
        """注册生命周期回调，在Agent创建完成后调用。"""
        lifecycle.register_before_message_generation(self._update_tool_availability)

    async def _update_tool_availability(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ) -> None:
        """根据当前LLM配置添加或移除load_image工具。"""
        should_have = self._current_llm_supports_image()
        has_tool = self._toolset.has_tool("load_image")

        if should_have and not has_tool:
            
            @self._toolset.register_tool(
                name="load_image",
                desc="加载图片文件并返回图片数据，用于多模态LLM查看图片内容",
                args={
                    "image_path": ToolArgInfo(
                        desc="图片文件的绝对路径", type="str"
                    ),
                },
                required_args=["image_path"],
            )
            def _load_image(image_path) -> ImageMessage:
                return load_image(image_path, self.group_chat)
        elif not should_have and has_tool:
            del self._toolset.tools["load_image"]

    def _current_llm_supports_image(self) -> bool:
        """检查当前LLM是否支持图像。"""
        from linhai.agent.main import Agent
        agent = self.group_chat.get_members("agent", Agent)
        llm = agent.get_current_model()
        return llm.support_image()