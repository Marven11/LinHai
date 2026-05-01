import json
from pathlib import Path

import linhai
from linhai.base import LanguageModelMessage, Message, register_message


@register_message
class DynamicFileContentMessage(Message):

    def __init__(self, filepath: str, show_line_numbers: bool):
        self.filepath = filepath
        self.show_line_numbers = show_line_numbers

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "user",
            "content": self.get_content(),
        }

    def get_content(self) -> str:
        path = Path(self.filepath)

        if not path.exists():
            return f"<<file_content>>\n<<filepath>>{self.filepath!r}<<filepath>>\n<<error>>文件不存在或已被移动/删除<<error>>\n<<file_content>>"

        if not path.is_file():
            return f"<<file_content>>\n<<filepath>>{self.filepath!r}<<filepath>>\n<<error>>路径不是文件<<error>>\n<<file_content>>"

        content = path.read_text()

        if self.show_line_numbers:
            lines = content.splitlines()
            numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
            formatted_content = "\n".join(numbered_lines)
        else:
            formatted_content = content
        return (
            "<<file_content>>\n<<message>>以下是文件的完整内容，不要重复读取！<<message>>"
            f"<<filepath>>{self.filepath!r}<<filepath>>\n<<content>>{formatted_content}<<content>>\n"
            "<<file_content>>"
        )

    def to_json(self) -> str:
        data = {
            "filepath": self.filepath,
            "show_line_numbers": self.show_line_numbers,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        return cls(
            filepath=data["filepath"],
            show_line_numbers=data["show_line_numbers"],
        )
