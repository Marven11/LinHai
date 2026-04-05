import json
import linhai
from pathlib import Path
from linhai.llm import (
    LanguageModelMessage,
    Message,
)


class GlobalPrompt(Message):

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        if not self.filepath.exists():
            return (
                f"<<global_prompt>><<message>>这是全局指导文档的路径和内容<<message>>\n"
                f"<<filepath>>{self.filepath.as_posix()!r}<<filepath>><<error>>文件不存在或已被移动/删除<<error>><<global_prompt>>"
            )
        content = self.filepath.read_text()
        return (
            f"<<global_prompt>><<message>>这是全局指导文档的路径和内容<<message>>\n"
            f"<<filepath>>{self.filepath.as_posix()!r}<<filepath>><<content>>{content}<<content>>\n"
            f"<<global_prompt>>"
        )

    def to_json(self) -> str:
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class PathPrompt(Message):

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        if not self.filepath.exists():
            return f"<<path_prompt>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>文件不存在或已被移动/删除<<error>>\n<<path_prompt>>"
        content = self.filepath.read_text()
        return f"<<path_prompt>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<path_prompt>>"

    def to_json(self) -> str:
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))


class ChecklistMessage(Message):

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        if not self.filepath.exists():
            return f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<error>>检查清单文件不存在或已被移动/删除<<error>>\n<<checklist>>"
        content = self.filepath.read_text()
        return f"<<checklist>>\n<<filepath>>{self.filepath.as_posix()!r}<<filepath>>\n<<content>>{content}<<content>>\n<<checklist>>"

    def to_json(self) -> str:
        data = {"filepath": str(self.filepath)}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        del registry
        data = json.loads(json_str)
        return cls(filepath=Path(data["filepath"]))
