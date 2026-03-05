"""Agent基础模块，包含运行时消息和全局指导类。"""

import hashlib
import json
from pathlib import Path
from reprlib import Repr
from typing import cast

import linhai
from linhai.llm import (
    LanguageModelMessage,
    Message,
)

from linhai.prompt import COMPRESS_RANGE_PROMPT

repr_obj = Repr()
repr_obj.maxstring = 100


WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class MessagesListSummerizeMessage(Message):
    """消息列表总结消息类，用于处理历史消息压缩的第一步。"""

    def __init__(
        self, messages_summerization: str, message_length: int, range_clean_id: str
    ):
        self.messages_summerization = messages_summerization
        self.message_length = message_length
        self.range_clean_id = range_clean_id
        self._valid = True

    def invalidate(self):
        self._valid = False

    def is_valid(self) -> bool:
        return self._valid

    def to_llm_message(self) -> LanguageModelMessage:
        if not self._valid:
            return {
                "role": "user",
                "content": f"[消息列表已无效，ID: {self.range_clean_id}]",
            }
        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUGGESTED_MESSAGE_COUNT|}", str(int(self.message_length * 0.5))
        ).replace("{|SUMMERIZATION|}", self.messages_summerization)
        return {
            "role": "user",
            "content": f"<<range_clean_summary>>\n"
            f"<<range_clean_id>>{self.range_clean_id}<<range_clean_id>>\n"
            f"<<message_count>>{self.message_length}<<message_count>>\n"
            f"<<content>>{prompt}<<content>>\n"
            f"<<range_clean_summary>>",
        }

    def to_json(self) -> str:
        data = {
            "messages_summerization": self.messages_summerization,
            "message_length": self.message_length,
            "range_clean_id": self.range_clean_id,
            "_valid": self._valid,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        data = json.loads(json_str)
        instance = cls(
            messages_summerization=data["messages_summerization"],
            message_length=data["message_length"],
            range_clean_id=data["range_clean_id"],
        )
        instance._valid = data.get("_valid", True)
        return instance


class RuntimeMessage(Message):
    """运行时消息，用于向LLM传递运行时信息。"""

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": f"<<runtime>>{self.message}<<runtime>>",
        }

    def to_json(self) -> str:

        data = {"role": "user", "message": self.message}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument

        data = json.loads(json_str)
        return cls(message=data["message"])


class GlobalPrompt:
    """全局指导类，用于读取和呈现全局指导文件内容。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将全局指导转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含全局指导内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "user",
                "content": "<<global_prompt>><<message>>这是全局指导文档的路径和内容<<message>>"
                f"<<filepath>>{self.filepath.as_posix()!r}<<filepath>><<content>>{content}<<content>><<global_prompt>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "content": "<<global_prompt>><<message>>这是全局指导文档的路径和内容<<message>>"
                f"<<filepath>>{self.filepath.as_posix()!r}<<filepath>><<error>>文件不存在或已被移动/删除<<error>><<global_prompt>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "content": "<<global_prompt>><<message>>这是全局指导文档的路径和内容<<message>>"
                f"<<filepath>>{self.filepath.as_posix()!r}<<filepath>><<error>>读取时发生错误: {str(e)}<<error>><<global_prompt>>",
            }

    def to_json(self) -> str:
        """
        将全局指导对象序列化为JSON字符串。

        返回:
            str: 包含文件路径的JSON字符串
        """
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """
        从JSON字符串反序列化全局指导对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（未使用，但为接口兼容性保留）

        返回:
            GlobalPrompt: 反序列化的全局指导对象
        """
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class ChecklistMessage:
    """检查清单消息类，用于读取和呈现检查清单文件内容。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将检查清单转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含检查清单内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "user",
                "content": f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<checklist>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "content": f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>检查清单文件不存在或已被移动/删除<<error>>\n<<checklist>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "content": f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>读取时发生错误: {str(e)}<<error>>\n<<checklist>>",
            }

    def to_json(self) -> str:
        """
        将检查清单对象序列化为JSON字符串。

        返回:
            str: 包含文件路径的JSON字符串
        """
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """
        从JSON字符串反序列化检查清单对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（未使用，但为接口兼容性保留）

        返回:
            ChecklistMessage: 反序列化的检查清单对象
        """
        del group_chat  # 未使用，但为接口兼容性保留
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class PathPrompt:
    """路径指导类，用于检测和呈现特定路径的文件内容。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将路径指导转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含路径指导内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "user",
                "content": f"<<path_prompt>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<path_prompt>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "content": f"<<path_prompt>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>文件不存在或已被移动/删除<<error>>\n<<path_prompt>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "content": f"<<path_prompt>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>读取时发生错误: {str(e)}<<error>>\n<<path_prompt>>",
            }

    def to_json(self) -> str:
        """
        将路径指导对象序列化为JSON字符串。

        返回:
            str: 包含文件路径的JSON字符串
        """
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """
        从JSON字符串反序列化路径指导对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（未使用，但为接口兼容性保留）

        返回:
            PathPrompt: 反序列化的路径指导对象
        """
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class FileContentMessage(Message):
    """文件内容消息，专门用于read_file工具返回的文件内容。"""

    def __init__(self, filepath: str, content: str, show_line_numbers: bool):
        self.filepath = filepath
        self.content = content
        self.show_line_numbers = show_line_numbers
        self._content_hash = hashlib.md5(content.encode()).hexdigest()
        self._resolved_path = Path(filepath).resolve()

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        if self.show_line_numbers:

            lines = self.content.splitlines()
            numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
            formatted_content = "\n".join(numbered_lines)
        else:
            formatted_content = self.content

        return {
            "role": "user",
            "content": "<<file_content>>\n<<message>>以下是文件的完整内容，不要重复读取！<<message>>"
            f"<<filepath>>{self.filepath!r}<<filepath>>\n<<content>>{formatted_content}<<content>>\n<<file_content>>",
        }

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {
            "filepath": self.filepath,
            "content": self.content,
            "show_line_numbers": self.show_line_numbers,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """从JSON字符串创建实例。"""
        data = json.loads(json_str)
        return cls(
            filepath=data["filepath"],
            content=data["content"],
            show_line_numbers=data["show_line_numbers"],
        )

    def __eq__(self, other: object) -> bool:
        """比较两个FileContentMessage是否相同，忽略行号差异。

        参数:
            other: 另一个对象

        返回:
            如果文件路径和内容（忽略行号）相同则返回True
        """
        if not isinstance(other, FileContentMessage):
            return False
        return (
            self.content == other.content
            and self._resolved_path == other._resolved_path
            and self.show_line_numbers == other.show_line_numbers
        )

    def __hash__(self) -> int:
        """哈希支持，用于set比较。基于标准化内容（忽略行号）计算哈希。"""
        normalized_hash = hash(self.content)
        return hash((self._resolved_path, normalized_hash))


class PreviousReasoningMessage(Message):
    """之前的思考内容消息，用于提供agent最近的思考内容参考。"""

    def __init__(self, reasoning_contents: list[str]):
        self.reasoning_contents = reasoning_contents

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。

        格式：
        <<previous_reasoning>><<message>>这是你之前的思考内容，仅做参考<<message>><<content>>xxx<<content>><<content>>xxx<<content>><<content>>xxx<<content>><<previous_reasoning>>
        """
        if not self.reasoning_contents:
            return {"role": "user", "content": ""}

        content_parts = []
        for reasoning_content in self.reasoning_contents:
            content_parts.append(f"<<content>>{reasoning_content}<<content>>")

        content = (
            f"<<previous_reasoning>><<message>>这是你之前的思考内容，仅做参考<<message>>"
            + "".join(content_parts)
            + "<<previous_reasoning>>"
        )
        return {"role": "user", "content": content}

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {"reasoning_contents": self.reasoning_contents}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """从JSON字符串创建实例。"""
        data = json.loads(json_str)
        return cls(reasoning_contents=data["reasoning_contents"])


class SpoofedReasoningMessage(Message):
    """伪造的推理消息，用于保留之前的推理内容。

    此消息的to_llm_message返回一个包含reasoning_content字段的字典，
    以便API提供商保留推理内容。
    """

    def __init__(self, reasoning_contents: list[str]):
        self.reasoning_contents = reasoning_contents

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。

        返回格式：
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "合并后的推理内容"
        }
        """

        reasoning_content = "\n".join(self.reasoning_contents)

        return cast(
            LanguageModelMessage,
            {
                "role": "assistant",
                "content": "",
                "reasoning_content": reasoning_content,
            },
        )

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {"reasoning_contents": self.reasoning_contents}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """从JSON字符串创建实例。"""
        data = json.loads(json_str)
        return cls(reasoning_contents=data["reasoning_contents"])
