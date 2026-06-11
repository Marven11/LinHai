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

from linhai.base import Message, register_message
from linhai.agent.lifecycle import Lifecycle
from linhai.type_hints import (
    LanguageModelMessage,
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartTextParam,
)
from linhai.registry import Registry
from linhai.utils.i18n import t
from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    FailedToolResult,
    ImageToolResult,
)

if TYPE_CHECKING:
    from linhai.machine_control import MachineControl


@register_message
class ImageDisplayMessage(Message):

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
        self.image_bytes = image_bytes
        self.mime_type = mime_type
        self.filename = filename
        self.registry = registry
        self.quality = quality
        self.width = width
        self.height = height

    def to_data_url(self) -> str:
        base64_data = base64.b64encode(self.image_bytes).decode("utf-8")
        return f"data:{self.mime_type};base64,{base64_data}"

    def save_to_temp_file(self) -> Path:
        suffix = Path(self.filename).suffix if self.filename else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(self.image_bytes)
            return Path(f.name)

    def to_llm_message(self) -> LanguageModelMessage:
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
            content = (
                f"<<image>><<message>>你不支持查看图片，图片内容已经自动转储到以下路径，"
                f"用其他适当的方式间接查看这张图片（{quality_desc}，估算token用量: {estimated_tokens}）"
                f"<<message>><<filepath>>{temp_path}<<filepath>><<image>>"
            )
            return {"role": "user", "content": content}

    def get_content(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"ImageDisplayMessage(size={len(self.image_bytes)} bytes, mime_type={self.mime_type}, quality={self.quality}, width={self.width}, height={self.height})"

    def estimated_tokens(self) -> int:
        import math

        tokens_h = math.ceil(self.height / 32)
        tokens_w = math.ceil(self.width / 32)
        return tokens_h * tokens_w

    def to_json(self) -> str:
        data = {
            "image_bytes": base64.b64encode(self.image_bytes).decode("utf-8"),
            "mime_type": self.mime_type,
            "filename": self.filename,
            "quality": self.quality,
            "width": self.width,
            "height": self.height,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str, registry: Registry) -> "ImageDisplayMessage":
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


async def _load_image_impl(
    image_filepath: str,
    quality: Literal["compressed", "raw"],
    machine_control: "MachineControl | None" = None,
) -> tuple[bytes, str, str | None, int, int]:
    temp_path: Path | None = None
    if machine_control is not None and machine_control.target_machine != "master_host":
        suffix = Path(image_filepath).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = Path(tmp.name)
        host = machine_control.machines[machine_control.target_machine]
        result = await host.download_file_concurrent(image_filepath, str(temp_path))
        if isinstance(result, FailedToolResult):
            os.unlink(temp_path)
            raise FileNotFoundError(
                f"从机器 {machine_control.target_machine} 下载图片失败: {result.content}"
            )
        path = temp_path
    else:
        if machine_control is not None:
            from linhai.machine_control.master_host import MasterHostControl

            master = machine_control.machines.get("master_host")
            if isinstance(master, MasterHostControl):
                path = master.resolve_path(image_filepath)
            else:
                path = Path(image_filepath)
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

    if temp_path is not None:
        os.unlink(temp_path)
    return image_bytes, mime_type, Path(image_filepath).name, width, height


async def load_image(
    image_filepath: str,
    registry: Registry,
    quality: Literal["compressed", "raw"],
    machine_control: "MachineControl | None" = None,
) -> ImageToolResult:
    """Load image from image_filepath and return ImageToolResult."""
    image_bytes, mime_type, filename, width, height = await _load_image_impl(
        image_filepath, quality, machine_control
    )
    return ImageToolResult(
        image_bytes_b64=base64.b64encode(image_bytes).decode("utf-8"),
        mime_type=mime_type,
        filename=filename,
        quality=quality,
        width=width,
        height=height,
    )


async def load_image_as_message(
    image_filepath: str,
    registry: Registry,
    quality: Literal["compressed", "raw"],
    machine_control: "MachineControl | None" = None,
) -> ImageDisplayMessage:
    image_bytes, mime_type, filename, width, height = await _load_image_impl(
        image_filepath, quality, machine_control
    )
    return ImageDisplayMessage(
        image_bytes=image_bytes,
        mime_type=mime_type,
        filename=filename,
        registry=registry,
        quality=quality,
        width=width,
        height=height,
    )


class MultimodalToolsetManager:

    def __init__(self, registry: Registry):
        self.registry = registry
        self.registry.register_member("multimodal_toolset_manager", self)
        self.toolset = ToolSet()

    def register_lifecycle(self, lifecycle: Lifecycle) -> None:
        lifecycle.before_message_generation.register(self._update_tool_availability)

    async def _update_tool_availability(self) -> None:
        should_have = self._current_llm_supports_image()
        has_tool = self.toolset.has_tool("load_image")

        if should_have and not has_tool:
            from linhai.agent.main import Agent
            from linhai.agent.messages import RuntimeMessage

            @self.toolset.register_tool(
                name="load_image",
                desc=t(
                    {
                        "zh_CN": "加载图片文件并返回图片数据，用于多模态LLM查看图片内容",
                        "en": "Load image file and return data for multimodal LLM to view",
                    }
                ),
                args={
                    "image_filepath": ToolArgInfo(
                        desc=t(
                            {
                                "zh_CN": "图片文件在当前机器的路径",
                                "en": "Image file path on current machine",
                            }
                        ),
                        schema={"type": "string"},
                    ),
                    "quality": ToolArgInfo(
                        desc=t(
                            {
                                "zh_CN": "图片质量，compressed表示压缩图像，raw表示原始图像",
                                "en": "Image quality, compressed for compressed image, raw for original",
                            }
                        ),
                        schema={"type": "string"},
                    ),
                },
                required_args=["image_filepath"],
            )
            async def _load_image(
                image_filepath, quality: Literal["compressed", "raw"] = "raw"
            ) -> ImageToolResult:
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
        from linhai.agent.main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm = agent.get_current_model()
        return llm.support_image()

    def serialize(self) -> dict:
        return {}

    def restore_from(self, data: dict) -> None:
        pass
