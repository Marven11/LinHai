"""Agent基础模块，包含运行时消息和全局记忆类。"""

from reprlib import Repr
from pathlib import Path
import json

import linhai
from linhai.llm import (
    Message,
    LanguageModelMessage,
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
            "content": f"<runtime>{prompt}</runtime>",
        }

    def to_json(self) -> str:

        data = {
            "messages_summerization": self.messages_summerization,
            "message_length": self.message_length,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):  # pylint: disable=unused-argument

        data = json.loads(json_str)
        return cls(
            messages_summerization=data["messages_summerization"],
            message_length=data["message_length"],
        )


class RuntimeMessage(Message):
    """运行时消息，用于向LLM传递运行时信息。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": f"<runtime>{self.message}</runtime>"}

    def to_json(self) -> str:

        data = {"role": "user", "message": self.message}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):  # pylint: disable=unused-argument

        data = json.loads(json_str)
        return cls(message=data["message"])


class DestroyedRuntimeMessage(Message):
    """被截断的运行时消息，表示消息已被截断。"""

    # pylint: disable=too-few-public-methods

    def __init__(self):
        pass

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": "<destroyed><runtime>本条消息已被截断</runtime></destroyed>",
        }

    def to_json(self) -> str:

        return json.dumps({})

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):  # pylint: disable=unused-argument
        return cls()


class GlobalMemory:
    """全局记忆类，用于读取和呈现全局记忆文件内容。"""

    # pylint: disable=too-few-public-methods

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
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，内容如下

{content}
""",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，但文件不存在或已被移动/删除
""",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，读取时发生错误: {str(e)}
""",
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
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):  # pylint: disable=unused-argument
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


class PathMemory:
    """路径记忆类，用于检测和呈现特定路径的文件内容。"""

    # pylint: disable=too-few-public-methods

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
                "content": f"""
# 路径记忆

文件位于{self.filepath.as_posix()!r}，内容如下

{content}
""",
            }
        except FileNotFoundError:
            return {
                "role": "user",
                "content": f"""
# 路径记忆

文件位于{self.filepath.as_posix()!r}，但文件不存在或已被移动/删除
""",
            }
        except (IOError, OSError) as e:
            return {
                "role": "user",
                "content": f"""
# 路径记忆

文件位于{self.filepath.as_posix()!r}，读取时发生错误: {str(e)}
""",
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
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):  # pylint: disable=unused-argument
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


from typing import TypedDict, NotRequired


class AgentContext(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    llms: list  # 多个LLM实例
    llm_names: list[str]  # LLM名称列表
    current_llm_index: int  # 当前使用的LLM索引
    compress_threshold_soft: int | float
    compress_threshold_hard: int | float
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段
    enable_directory_change_detection: NotRequired[bool]  # 是否启用目录更改检测