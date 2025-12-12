"""Agent基础模块，包含运行时消息和全局记忆类。"""

import hashlib
import re
import json
from pathlib import Path
from reprlib import Repr
from typing import NotRequired, TypedDict

import linhai
from linhai.llm import (
    LanguageModelMessage,
    Message,
)

from linhai.prompt import COMPRESS_RANGE_PROMPT

repr_obj = Repr()
repr_obj.maxstring = 100


WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class CompressRangeRequest(Message):
    """压缩范围请求消息类，用于处理历史消息压缩。"""

    def __init__(self, messages_summerization: str, message_length: int):
        self.messages_summerization = messages_summerization
        self.message_length = message_length

    def to_llm_message(self) -> LanguageModelMessage:

        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUMMERIZATION|}", self.messages_summerization
        ).replace("{|SUGGESTED_MESSAGE_COUNT|}", str(int(self.message_length * 0.5)))
        return {
            "role": "user",
            "name": "runtime",
            "content": f"<<runtime>>{prompt}<<runtime>>",
        }

    def to_json(self) -> str:

        data = {
            "messages_summerization": self.messages_summerization,
            "message_length": self.message_length,
        }
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument

        data = json.loads(json_str)
        return cls(
            messages_summerization=data["messages_summerization"],
            message_length=data["message_length"],
        )


class RuntimeMessage(Message):
    """运行时消息，用于向LLM传递运行时信息。"""

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "name": "runtime",
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


class GlobalMemory:
    """全局记忆类，用于读取和呈现全局记忆文件内容。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将全局记忆转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含全局记忆内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "user",
                "name": "global-memory",
                "content": f"<<global_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<global_memory>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "name": "global-memory",
                "content": f"<<global_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>文件不存在或已被移动/删除<<error>>\n<<global_memory>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "name": "global-memory",
                "content": f"<<global_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>读取时发生错误: {str(e)}<<error>>\n<<global_memory>>",
            }

    def to_json(self) -> str:
        """
        将全局记忆对象序列化为JSON字符串。

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
        从JSON字符串反序列化全局记忆对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（未使用，但为接口兼容性保留）

        返回:
            GlobalMemory: 反序列化的全局记忆对象
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
                "name": "checklist",
                "content": f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<checklist>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "name": "checklist",
                "content": f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>检查清单文件不存在或已被移动/删除<<error>>\n<<checklist>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "name": "checklist",
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
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        """
        从JSON字符串反序列化检查清单对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（为接口兼容性保留）

        返回:
            ChecklistMessage: 反序列化的检查清单对象
        """
        del group_chat  # 未使用，但为接口兼容性保留
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class PathMemory:
    """路径记忆类，用于检测和呈现特定路径的文件内容。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将路径记忆转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含路径记忆内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "user",
                "name": "path-memory",
                "content": f"<<path_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<path_memory>>",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "name": "path-memory",
                "content": f"<<path_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>文件不存在或已被移动/删除<<error>>\n<<path_memory>>",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "name": "path-memory",
                "content": f"<<path_memory>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>读取时发生错误: {str(e)}<<error>>\n<<path_memory>>",
            }

    def to_json(self) -> str:
        """
        将路径记忆对象序列化为JSON字符串。

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
        从JSON字符串反序列化路径记忆对象。

        参数:
            json_str: JSON格式的字符串
            group_chat: GroupChat实例（未使用，但为接口兼容性保留）

        返回:
            PathMemory: 反序列化的路径记忆对象
        """
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class AgentContext(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    llms: list
    llm_names: list[str]
    current_llm_index: int
    compress_threshold: int | float
    memory: NotRequired[dict]
    enable_directory_change_detection: NotRequired[bool]


class FileContentMessage(Message):
    """文件内容消息，专门用于read_file工具返回的文件内容。"""

    def __init__(self, filepath: str, content: str):
        self.filepath = filepath
        self.content = content
        self._content_hash = hashlib.md5(content.encode()).hexdigest()
        self._resolved_path = Path(filepath).resolve()

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        return {
            "role": "user",
            "name": "file-content",
            "content": f"<<file_content>>\n<<message>>以下是文件的完整内容，不要重复读取！<<message>><<filepath>>{self.filepath!r}<<filepath>>\n<<content>>{self.content}<<content>>\n<<file_content>>",
        }

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        data = {"filepath": self.filepath, "content": self.content}
        return json.dumps(data)

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ):  # pylint: disable=unused-argument
        """从JSON字符串创建实例。"""
        data = json.loads(json_str)
        return cls(filepath=data["filepath"], content=data["content"])

    def __eq__(self, other: object) -> bool:
        """比较两个FileContentMessage是否相同，忽略行号差异。

        参数:
            other: 另一个对象

        返回:
            如果文件路径和内容（忽略行号）相同则返回True
        """
        if not isinstance(other, FileContentMessage):
            return False
        if self._resolved_path != other._resolved_path:
            return False
        if self.content == other.content:
            return True
        return self._normalize_content(self.content) == self._normalize_content(
            other.content
        )

    @staticmethod
    def _normalize_content(content: str) -> str:
        """标准化文件内容，移除行号前缀。

        匹配read_file工具添加的行号格式：行首的数字后跟冒号和空格。
        例如：'1: content' -> 'content'
        """
        return re.sub(r"^\d+: ", "", content, flags=re.MULTILINE)

    def __hash__(self) -> int:
        """哈希支持，用于set比较。基于标准化内容（忽略行号）计算哈希。"""
        normalized_content = self._normalize_content(self.content)
        normalized_hash = hash(normalized_content)
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
            return {"role": "user", "name": "previous-reasoning", "content": ""}

        content_parts = []
        for reasoning_content in self.reasoning_contents:
            content_parts.append(f"<<content>>{reasoning_content}<<content>>")

        content = (
            f"<<previous_reasoning>><<message>>这是你之前的思考内容，仅做参考<<message>>"
            + "".join(content_parts)
            + "<<previous_reasoning>>"
        )
        return {"role": "user", "name": "previous-reasoning", "content": content}

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
