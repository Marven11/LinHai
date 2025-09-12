"""Agent基础模块，包含运行时消息和全局记忆类。"""

from reprlib import Repr
from pathlib import Path

from linhai.llm import (
    Message,
    LanguageModelMessage,
)

from linhai.prompt import COMPRESS_RANGE_PROMPT

repr_obj = Repr(maxstring=100)


WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class CompressRangeRequest(Message):
    """压缩范围请求消息类，用于处理历史消息压缩。"""

    def __init__(self, messages_summerization: str, message_length: int):
        self.messages_summerization = messages_summerization
        self.message_length = message_length

    def to_llm_message(self) -> LanguageModelMessage:

        prompt = COMPRESS_RANGE_PROMPT.replace(
            "{|SUMMERIZATION|}", self.messages_summerization
        ).replace("{|SUGGESTED_MESSAGE_COUNT|}", str(int(self.message_length * 0.8)))
        return {
            "role": "user",
            "content": f"<runtime>{prompt}</runtime>",
        }


class RuntimeMessage(Message):
    """运行时消息，用于向LLM传递运行时信息。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": f"<runtime>{self.message}</runtime>"}


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
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，内容如下

{content}
""",
            }
        except FileNotFoundError:
            return {
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，但文件不存在或已被移动/删除
""",
            }
        except (IOError, OSError) as e:
            return {
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，读取时发生错误: {str(e)}
""",
            }
