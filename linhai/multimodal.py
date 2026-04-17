"""多模态支持模块。

包含ImageMessage消息类，load_image工具，以及动态工具集管理。
"""

from __future__ import annotations
import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Literal
from PIL import Image
from io import BytesIO

from typing import TYPE_CHECKING

from linhai.base import Message
from linhai.agent.lifecycle import Lifecycle
from linhai.type_hints import LanguageModelMessage
from linhai.registry import Registry

if TYPE_CHECKING:
    from linhai.machine_control import MachineControl


class ImageMessage(Message):
    """图片消息类，在内存中保存图片bytes数据。"""

    def __init__(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str | None,
        registry: Registry,
        width: int,
        height: int,
        quality: Literal["compressed", "raw"] = "raw",
    ):
        """初始化图片消息。

        Args:
            image_bytes: 图片的二进制数据
            mime_type: 图片的MIME类型
            filename: 原始文件名（可选，None表示未知）
            registry: Registry实例（用于动态获取LLM支持状态）
            width: 图片宽度
            height: 图片高度
            quality: 图片质量，"compressed"表示压缩图像，"raw"表示原始图像（默认）
        """
        self.image_bytes = image_bytes
        self.mime_type = mime_type
        self.filename = filename
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
        suffix = Path(self.filename).suffix if self.filename else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(self.image_bytes)
            return Path(f.name)

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。

        动态检查当前LLM是否支持图像，如果支持则返回image_url格式，
        否则保存到临时文件并返回文本消息。

        严格按照_current_llm_supports_image的方法获取LLM支持状态：
        - 通过self.registry获取agent
        - 调用agent.get_current_model()获取当前llm
        - 调用llm.support_image()获取支持状态

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
                        "type": "image_url",
                        "image_url": {"url": self.to_data_url()},
                    }
                ],
            }
        else:
            temp_path = self.save_to_temp_file()
            estimated_tokens = self.estimated_tokens()
            quality_desc = "原始分辨率" if self.quality == "raw" else "压缩后"
            content = f"<<image>><<message>>你不支持查看图片，图片内容已经自动转储到以下路径，用其他适当的方式间接查看这张图片（{quality_desc}，估算token用量: {estimated_tokens}）<<message>><<filepath>>{temp_path}<<filepath>><<image>>"
            return {"role": "user", "content": content}

    def get_content(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"ImageMessage(size={len(self.image_bytes)} bytes, mime_type={self.mime_type}, quality={self.quality}, width={self.width}, height={self.height})"

    def estimated_tokens(self) -> int:
        import math

        tokens_h = math.ceil(self.height / 32)
        tokens_w = math.ceil(self.width / 32)
        return tokens_h * tokens_w

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {
            "image_bytes": base64.b64encode(self.image_bytes).decode("utf-8"),
            "mime_type": self.mime_type,
            "filename": self.filename,
            "quality": self.quality,
            "width": self.width,
            "height": self.height,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: Registry) -> "ImageMessage":
        """从JSON字符串创建ImageMessage实例。"""
        data = json.loads(json_str)
        image_bytes = base64.b64decode(data["image_bytes"])
        return cls(
            image_bytes=image_bytes,
            mime_type=data.get("mime_type", "image/png"),
            filename=data.get("filename"),
            registry=registry,
            quality=data.get("quality", "raw"),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )


async def load_image(
    image_filepath: str,
    registry: Registry,
    quality: Literal["compressed", "raw"],
    machine_control: "MachineControl | None" = None,
) -> ImageMessage:
    """加载图片文件并返回ImageMessage。

    Args:
        image_filepath: 图片文件路径
        registry: Registry实例（用于动态获取LLM支持状态）
        quality: 图片质量，"compressed"表示压缩图像，"raw"表示原始图像（默认）
        machine_control: MachineControl实例（可选，用于支持远程机器读取）

    Returns:
        ImageMessage: 包含图片数据的消息对象

    Raises:
        FileNotFoundError: 图片文件不存在
        ValueError: 图像文件损坏或格式不支持
    """
    from linhai.tool.base import ToolResultFailed

    temp_path: Path | None = None
    if machine_control is not None and machine_control.target_machine != "master_host":
        suffix = Path(image_filepath).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = Path(tmp.name)
        host = machine_control.machines[machine_control.target_machine]
        result = await host.download_file_concurrent(image_filepath, str(temp_path))
        if isinstance(result, ToolResultFailed):
            os.unlink(temp_path)
            raise FileNotFoundError(
                f"从机器 {machine_control.target_machine} 下载图片失败: {result.content}"
            )
        path = temp_path
    else:
        path = Path(image_filepath)

    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在: {image_filepath}")

    with Image.open(path) as img_for_verify:
        img_for_verify.verify()

    with Image.open(path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        width, height = img.size

        if quality == "compressed":
            target_area = 512 * 512
            current_area = width * height
            if current_area > target_area:
                scale = (target_area / current_area) ** 0.5
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)
                width, height = img.size
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            image_bytes = buffer.getvalue()
            mime_type = "image/jpeg"
        else:
            buffer = BytesIO()
            img_format = img.format.upper() if img.format else "PNG"

            if img_format in ("JPEG", "JPG"):
                img.save(buffer, format="JPEG")
                mime_type = "image/jpeg"
            elif img_format == "PNG":
                img.save(buffer, format="PNG")
                mime_type = "image/png"
            elif img_format == "WEBP":
                if img.info.get("lossless", 0):
                    img.save(buffer, format="PNG")
                    mime_type = "image/png"
                else:
                    img.save(buffer, format="JPEG", quality=95)
                    mime_type = "image/jpeg"
            else:
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(buffer, format="JPEG", quality=95)
                mime_type = "image/jpeg"
            image_bytes = buffer.getvalue()

    result = ImageMessage(
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=Path(image_filepath).name,
        registry=registry,
        quality=quality,
        width=width,
        height=height,
    )
    if temp_path is not None:
        os.unlink(temp_path)
    return result


from linhai.tool.base import ToolSet, ToolArgInfo


class MultimodalToolsetManager:
    """多模态工具集管理器，根据当前LLM配置动态调整工具集。

    设计原则：
    - 创建一个ToolSet用于存放load_image工具
    - 在初始化时添加到ToolManager
    - 根据LLM配置动态添加/移除工具，而不是整个ToolSet
    """

    def __init__(self, registry: Registry):
        """初始化多模态工具集管理器。"""
        self.registry = registry
        self.registry.register_member("multimodal_toolset_manager", self)

        self.toolset = ToolSet()

    def register_lifecycle(self, lifecycle: Lifecycle) -> None:
        """注册生命周期回调，在Agent创建完成后调用。"""
        lifecycle.before_message_generation.register(self._update_tool_availability)

    async def _update_tool_availability(self) -> None:
        """根据当前LLM配置添加或移除load_image工具。"""
        should_have = self._current_llm_supports_image()
        has_tool = self.toolset.has_tool("load_image")

        if should_have and not has_tool:
            from linhai.agent.main import Agent
            from linhai.agent.messages import RuntimeMessage

            @self.toolset.register_tool(
                name="load_image",
                desc="加载图片文件并返回图片数据，用于多模态LLM查看图片内容",
                args={
                    "image_filepath": ToolArgInfo(
                        desc="图片文件在当前机器的路径", type="str"
                    ),
                    "quality": ToolArgInfo(
                        desc="图片质量，compressed表示压缩图像，raw表示原始图像",
                        type="str",
                    ),
                },
                required_args=["image_filepath"],
            )
            async def _load_image(
                image_filepath, quality: Literal["compressed", "raw"] = "raw"
            ) -> ImageMessage:
                from linhai.machine_control import MachineControl

                machine_control: MachineControl | None = None
                if self.registry.has_member("machine_control"):
                    machine_control = self.registry.get_member_typechecked(
                        "machine_control", MachineControl
                    )
                return await load_image(
                    image_filepath, self.registry, quality, machine_control
                )

            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage("当前LLM支持多模态，已添加load_image工具")
            )

        elif not should_have and has_tool:
            from linhai.agent.main import Agent
            from linhai.agent.messages import RuntimeMessage

            del self.toolset.tools["load_image"]

            agent = self.registry.get_member_typechecked("agent", Agent)
            await agent.message_processor.add_new_message(
                RuntimeMessage("当前LLM不支持多模态，已移除load_image工具")
            )

    def _current_llm_supports_image(self) -> bool:
        """检查当前LLM是否支持图像。"""
        from linhai.agent.main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm = agent.get_current_model()
        return llm.support_image()
