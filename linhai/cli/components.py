"""CLI UI components for LinHai agent."""

import colorsys
import json
import re
import time
from typing import Union

from rich.markup import escape
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Static

from linhai.streamjson.main import StreamJsonParser, Value, ValuePiece
from linhai.tool.tools.todolist import TodolistItem

REFRESH_INTERVAL = 0.05

StoppableWidget = Union[
    "ToolCallWidget", "NormalContentWidget", "ReasoningContentWidget"
]

EXTENSION_TO_TYPE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".pl": "perl",
    ".lua": "lua",
    ".r": "r",
    ".m": "matlab",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".csv": "csv",
    ".tsv": "tsv",
    ".dockerfile": "dockerfile",
    ".gitignore": "gitignore",
    ".gitattributes": "gitattributes",
    ".dockerignore": "dockerignore",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".sql": "sql",
    ".psql": "sql",
    ".txt": "text",
    ".log": "text",
}

ASCII_ART = r"""
  █████       █████ ██████   █████ █████   █████   █████████   █████
 ▒▒███       ▒▒███ ▒▒██████ ▒▒███ ▒▒███   ▒▒███   ███▒▒▒▒▒███ ▒▒███
  ▒███        ▒███  ▒███▒███ ▒███  ▒███    ▒███  ▒███    ▒███  ▒███
  ▒███        ▒███  ▒███▒▒███▒███  ▒███████████  ▒███████████  ▒███
  ▒███        ▒███  ▒███ ▒▒██████  ▒███▒▒▒▒▒███  ▒███▒▒▒▒▒███  ▒███
  ▒███      █ ▒███  ▒███  ▒▒█████  ▒███    ▒███  ▒███    ▒███  ▒███
  ███████████ █████ █████  ▒▒█████ █████   █████ █████   █████ █████
 ▒▒▒▒▒▒▒▒▒▒▒ ▒▒▒▒▒ ▒▒▒▒▒    ▒▒▒▒▒ ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒   ▒▒▒▒▒ ▒▒▒▒▒
"""


class RainbowAsciiArt(Static):
    """显示斜向彩虹渐变色ASCII艺术的组件"""

    DEFAULT_CSS = """
    RainbowAsciiArt {
        width: 100%;
        text-align: center;
        content-align: center middle;
    }
    """

    def __init__(self, ascii_art: str):
        super().__init__()
        self.ascii_art = ascii_art
        self.time_index = 0
        self.last_call_time = time.perf_counter()
        self.slow_counter = 0
        self.rainbow_colors: list[Style] = self._generate_rainbow_colors()

    def _generate_rainbow_colors(self) -> list[Style]:
        """使用HSL颜色空间生成平滑的彩虹颜色样式列表"""
        num_colors = 256
        styles = []
        for i in range(num_colors):

            hue = i / num_colors
            rgb = colorsys.hls_to_rgb(hue, 0.5, 0.8)

            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)
            styles.append(Style(color=f"rgb({r},{g},{b})"))
        mid = len(styles) // 2
        styles = styles[mid:] + styles[:mid]
        return styles

    def on_mount(self) -> None:
        """组件挂载时启动动画"""
        self.set_interval(REFRESH_INTERVAL, self._update_animation)

    def _update_animation(self) -> None:
        """更新动画时间索引并重新渲染"""
        self.time_index += 1

        if time.perf_counter() - self.last_call_time > 0.2:
            self.slow_counter += 1

        self.last_call_time = time.perf_counter()
        if self.slow_counter > 3:
            return
        elif self.slow_counter > 0:
            self.slow_counter -= 1

        self.update(self._render_ascii_art())

    def _render_ascii_art(self) -> Text:
        """渲染带斜向彩虹渐变色的ASCII艺术"""
        text = Text()
        lines = self.ascii_art.splitlines()
        for row, line in enumerate(lines):
            for col, char in enumerate(line):

                color_index = (
                    (row + col + self.time_index) // 2 % len(self.rainbow_colors)
                )
                style = self.rainbow_colors[color_index]
                text.append(char, style=style)
            if row < len(lines) - 1:
                text.append("\n")
        return text


class AnimatedWelcomeWidget(Static):
    """动画欢迎信息组件"""

    DEFAULT_CSS = """
    AnimatedWelcomeWidget {
        width: 100%;
        text-align: center;
        content-align: center middle;
    }
    """

    def __init__(self, version: str, llm_name: str):
        super().__init__()
        self.version = version
        self.llm_name = llm_name
        self.animation_stage = 0
        self.elapsed_time = 0.0
        self.daily_quote = "/time set 0"
        self.version_info = f"{self.version} | LLM: {self.llm_name}"
        self.timer: Timer | None = None

    def on_mount(self) -> None:
        """组件挂载时启动动画"""
        self.timer = self.set_interval(0.05, self._update_animation)

    def _update_animation(self) -> None:
        """更新动画"""
        self.elapsed_time += 0.05
        if self.elapsed_time >= 0.2:
            self.animation_stage = 1
        if self.elapsed_time >= 1.0:
            self.animation_stage = 2
        if self.animation_stage == 0:

            self.update(self._render_daily_quote())
        elif self.animation_stage == 1:
            self.update(self._render_glitch())
        else:
            self.update(self._render_version_info())
            if self.timer:
                self.timer.stop()

    def _render_daily_quote(self) -> Text:
        """渲染每日一言"""
        text = Text()
        text.append(self.daily_quote, style=Style(color="rgb(255, 215, 0)", bold=True))
        return text

    def _render_glitch(self) -> Text:
        """渲染乱码效果，颜色从黄色渐变到灰色"""
        import random

        text = Text()
        glitch_text = escape(
            "".join(
                random.choice("!@#$%^&*()_+-=[]{}|;:,.<>?/~`")
                for _ in range(max(len(self.daily_quote), len(self.version_info)))
            )
        )

        saturation = max(0, 1.2 - self.elapsed_time)
        lightness = 0.5
        hue = 50.59 / 360

        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        r = int(rgb[0] * 255)
        g = int(rgb[1] * 255)
        b = int(rgb[2] * 255)

        text.append(glitch_text, style=Style(color=f"rgb({r},{g},{b})", bold=True))
        return text

    def _render_version_info(self) -> Text:
        """渲染版本信息"""
        text = Text()
        text.append(self.version_info, style=Style(color="rgb(127,127,127)", bold=True))
        return text


class RuntimeMessageWidget(Static):
    """运行时消息显示组件"""

    DEFAULT_CSS = """
    RuntimeMessageWidget {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, level: str, content: str):
        super().__init__()
        self.level = level
        self.content = content

    def compose(self) -> ComposeResult:
        """组合UI组件"""

        level_style = {"INFO": "#4C566A", "WARNING": "#EBCB8B", "ERROR": "#BF616A"}.get(
            self.level, "#4C566A"
        )

        message_text = Text()
        message_text.append(f"[{self.level[0]}]", style=level_style)
        message_text.append(f" {self.content}")

        yield Static(message_text)


class ToolCallWidget(Static):
    """工具调用显示组件，流式显示键值对表格"""

    DEFAULT_CSS = """
    ToolCallWidget {
        width: 100%;
        overflow: hidden;
        padding-left: 1;
        padding-right: 1;
        border-title-align: left;
        border-title-color: $accent;
        border: solid $accent;
    }

    ToolCallWidget.error {
        border-title-color: red;
        border: solid red;
    }
    """

    def __init__(self, json_str: str):
        super().__init__()
        self.json_str = json_str
        self.parser = StreamJsonParser()

        self.timer: Timer | None = None

        self.guessed_content_type = ""
        self.current_content = ""
        self.content_before_current_value = ""
        self.current_key = ""
        self.current_value = ""
        self.has_error = False
        self.error_message = ""

        self.border_title = "tool call"

    def finish_streaming(self) -> None:
        """停止组件的timer"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        self.update_display()

    def feed_string(self, new_content: str):
        try:
            self.json_str += new_content
            self.parser.feed_string(new_content)
        except RuntimeError as e:

            self.has_error = True
            self.error_message = str(e)

    def is_current_data_finished(self):
        return self.parser.is_current_data_finished()

    def on_mount(self) -> None:
        """组件挂载时开始解析JSON"""
        self.timer = self.set_interval(REFRESH_INTERVAL, self.update_display)

        try:
            self.parser.feed_string(self.json_str)
        except RuntimeError as e:
            self.has_error = True
            self.error_message = str(e)

    def update_display(self) -> None:
        """更新显示"""

        if self.has_error:

            self.update(
                Syntax(
                    self.json_str,
                    lexer="markdown",
                    theme="nord-darker",
                    background_color="#2E3440",
                    word_wrap=True,
                )
            )
            self.border_title = "tool call (error)"
            self.add_class("error")
            return

        try:
            for value in self.parser:
                if value.index_key != self.current_key:
                    self.current_key = value.index_key
                    self.content_before_current_value = self.current_content
                    self.current_content += f"{self.current_key}: `"

                if isinstance(value, Value):
                    final_value = (
                        value.value
                        if isinstance(value.value, str)
                        else json.dumps(value.value)
                    )

                    new_guessed_type = self._guess_content_type(final_value)
                    if not self.guessed_content_type or new_guessed_type:
                        self.guessed_content_type = new_guessed_type

                    if "\n" in final_value:
                        backticks = "`" * self.get_backtick_count(final_value)
                        self.current_content = (
                            self.content_before_current_value
                            + f"{self.current_key}:\n\n{backticks}{self.guessed_content_type}\n{final_value}\n{backticks}\n\n"
                        )
                    else:
                        self.current_content = (
                            self.content_before_current_value
                            + f"{self.current_key}: `{final_value}`\n"
                        )

                    self.current_value = ""

                elif isinstance(value, ValuePiece):
                    self.current_value += value.char
                    if "\n" in self.current_value:
                        backtick_count = self.get_backtick_count(self.current_value)
                        backticks = "`" * backtick_count
                        self.current_content = (
                            self.content_before_current_value
                            + f"{self.current_key}:\n\n{backticks}{self.guessed_content_type}\n{self.current_value}\n{backticks}"
                        )
                    else:
                        self.current_content = (
                            self.content_before_current_value
                            + f"{self.current_key}: `{self.current_value}`"
                        )

                self.update(
                    Syntax(
                        self.current_content.strip(),
                        lexer="markdown",
                        theme="nord-darker",
                        background_color="#2E3440",
                        word_wrap=True,
                    )
                )
        except RuntimeError as e:

            self.has_error = True
            self.error_message = str(e)

            self.update_display()

    def get_backtick_count(self, text: str) -> int:
        """计算所需的反引号数量，确保至少比文本中连续反引号的最大数量多1，且至少为3"""
        matches = re.findall(r"^`+", text, re.MULTILINE)
        if matches:
            max_count = max(len(match) for match in matches)
        else:
            max_count = 0
        return max(3, max_count + 1)

    def _guess_content_type(self, value: str) -> str:
        """根据文件后缀名猜测接下来或当前的文件类型"""
        for ext, content_type in EXTENSION_TO_TYPE.items():
            if value.endswith(ext):
                return content_type

        if re.match("^(GET|POST|PUT|DELETE|HEAD|OPTION)", value):
            return "http"

        return ""


class ReasoningContentWidget(Static):
    """思考消息显示组件，不换行并用省略号省略超出行"""

    DEFAULT_CSS = """
    ReasoningContentWidget {
        width: 100%;
        overflow: hidden;
        border-title-color: grey;
        border-title-align: left;
        border: solid grey;
        padding-left: 1;
        padding-right: 1;
    }

    ReasoningContentWidget.reasoning-widget-collapsed {
        text-overflow: ellipsis;
        text-wrap: nowrap;
    }
    
    ReasoningContentWidget.reasoning-widget-expanded {
        height: auto;
        text-overflow: fold;
        text-wrap: wrap;
    }
    """

    def __init__(self, role: str, content: str, sender_name: str):
        super().__init__()
        self.role = f"{role}-reasoning"
        self.content_str = content
        self.is_expanded = False
        self.timer: Timer | None = None
        self.sender_name = sender_name
        self.border_title = self.calculate_border_title()
        self.add_class("reasoning-widget-collapsed")

    def feed_string(self, new_content: str):
        """追加内容到消息"""
        self.content_str += new_content

    def append_content(self, new_content: str):
        """追加内容到消息（兼容性方法）"""
        self.feed_string(new_content)

    def calculate_border_title(self) -> str:
        return f"{self.sender_name} (reasoning) {'[点击隐藏]' if self.is_expanded else '[点击展开]'}"

    def on_click(self):
        if self.is_expanded:
            self.is_expanded = False
            self.remove_class("reasoning-widget-expanded")
            self.add_class("reasoning-widget-collapsed")
        else:
            self.is_expanded = True
            self.add_class("reasoning-widget-expanded")
            self.remove_class("reasoning-widget-collapsed")

        self.border_title = self.calculate_border_title()
        self.update_display()

    def on_mount(self) -> None:
        """组件挂载时开始显示"""
        self.timer = self.set_interval(REFRESH_INTERVAL, self.update_display)

    def finish_streaming(self) -> None:
        """停止组件的timer"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        self.update_display()

    def update_display(self) -> None:
        """更新思考消息显示"""
        content_to_display = self.content_str.strip()

        if self.is_expanded:
            renderable = Syntax(
                content_to_display,
                lexer="markdown",
                theme="nord-darker",
                background_color="#2E3440",
                word_wrap=True,
            )
        else:
            lines = [line for line in content_to_display.splitlines() if line]
            truncated_content = "\n".join(lines[-2:]) if lines else ""
            renderable = Text(truncated_content, overflow="ellipsis", no_wrap=True)

        self.update(renderable)


class NormalContentWidget(Static):
    """普通消息显示组件，按字符换行"""

    DEFAULT_CSS = """
    NormalContentWidget {
        width: 100%;
        overflow: hidden;
        padding-left: 1;
        padding-right: 1;
        border-title-align: left;
        border-title-color: grey;
        border: solid grey;
    }

    NormalContentWidget.user-message {
        border-title-color: #A3BE8C;
        border: solid #A3BE8C;
    }

    NormalContentWidget.assistant-message {
        border-title-color: $primary;
        border: solid $primary;
    }
    """

    def __init__(self, role: str, content: str, sender_name: str):
        super().__init__()
        self.content_str = content
        self.display_name = sender_name
        self.role = role
        self.timer: Timer | None = None
        self._content_static: Static | None = None
        self.add_class(f"{self.role}-message")
        self.border_title = self.display_name

    def finish_streaming(self) -> None:
        """停止组件的timer"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        self.update_display()

    def feed_string(self, new_content: str):
        """追加内容到消息"""
        self.content_str += new_content

    def on_mount(self) -> None:
        """组件挂载时开始显示"""
        self._content_static = Static("")
        self.mount(self._content_static)
        self.timer = self.set_interval(REFRESH_INTERVAL, self.update_display)

    def update_display(self) -> None:
        """更新普通消息显示，按字符换行"""
        content_to_display = self.content_str.strip()

        if self._content_static is not None:
            self._content_static.update(
                Syntax(
                    content_to_display,
                    lexer="markdown",
                    theme="nord-darker",
                    background_color="#2E3440",
                    word_wrap=True,
                )
            )


class MessageWidget(Static):
    """普通消息显示组件，支持流式token处理和JSON工具调用显示"""

    def __init__(self, role: str, content: str, sender_name: str):
        super().__init__()
        self.role = role
        self.initial_content = content
        self.sender_name = sender_name
        self.content_str = content

        self.current_widget: ToolCallWidget | NormalContentWidget | None = None

        self.current_line = ""

    def update_display(self):
        self.append_content("")

    def finish_streaming(self) -> None:
        """停止组件的timer"""
        if self.current_widget and isinstance(
            self.current_widget, (ToolCallWidget, NormalContentWidget)
        ):
            self.current_widget.finish_streaming()

    def stop_old_widget(self, old_widget: ToolCallWidget | NormalContentWidget):
        def stop_timer():
            if old_widget.timer:
                old_widget.timer.stop()

        self.set_timer(5, stop_timer)

    def feed_string(self, new_content: str):
        """追加内容到消息"""
        self.append_content(new_content)

    def append_content(self, new_content: str):
        if self.current_widget is None:
            self.current_widget = NormalContentWidget(
                self.role,
                "",
                self.sender_name,
            )
            self.mount(self.current_widget)
            self.append_content(self.initial_content)
        for line in new_content.splitlines(keepends=True):
            new_content, new_widget = self.handle_line(line)
            self.current_widget.feed_string(new_content)
            if new_widget is not None:
                self.stop_old_widget(self.current_widget)
                self.current_widget = new_widget
                self.mount(self.current_widget)

    def handle_line(
        self, line: str
    ) -> tuple[str, ToolCallWidget | NormalContentWidget | None]:
        self.current_line += line
        if self.current_line.startswith("`"):
            if not self.current_line.endswith("\n"):
                return "", None
            if isinstance(self.current_widget, NormalContentWidget):
                if self.current_line == "```json toolcall\n":
                    self.current_line = ""
                    return "", ToolCallWidget("")
                else:
                    whole_line = self.current_line
                    self.current_line = ""
                    return whole_line, None
            else:
                whole_line = self.current_line
                self.current_line = ""
                return "", NormalContentWidget(
                    self.role,
                    "" if whole_line == "```\n" else whole_line,
                    self.sender_name,
                )
        else:
            if self.current_line.endswith("\n"):
                self.current_line = ""
            return line, None


class FooterWidget(Static):
    """CLI底栏组件，自动刷新显示token和消息统计信息"""

    DEFAULT_CSS = """
    FooterWidget {
        background: $background-darken-1;
        color: $foreground-darken-3;
    }
    """

    def __init__(self, group_chat, token_manager, use_nerd_font=False):
        super().__init__("")
        self.group_chat = group_chat
        self.token_manager = token_manager
        self.use_nerd_font = use_nerd_font
        self.current_answer_token = 0
        self.timer = None

    def on_mount(self):
        """组件挂载时启动定时刷新"""
        self.timer = self.set_interval(1.0, self.update_display)

    def on_unmount(self):
        """组件卸载时停止定时器，避免内存泄漏"""
        if self.timer:
            self.timer.stop()

    def update_token_info(self, current_answer_token: int):
        """更新当前answer的token用量"""
        self.current_answer_token = current_answer_token

    def update_display(self):
        """
        更新底栏显示内容。

        自动获取当前token用量和消息统计信息，并在没有token信息时显示默认消息。
        优化刷新逻辑，只在需要时更新显示。
        """
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        if agent is None:
            self.update("Agent未初始化")
            return

        display_text = self.token_manager.get_token_display_text(
            agent, self.current_answer_token, self.use_nerd_font
        )

        self.update(display_text)


class TodolistWidget(Static):
    """Todolist显示widget。"""

    DEFAULT_CSS = """
    TodolistWidget {
        width: auto;
        height: auto;
        background: #3B4252;
        border: solid #88C0D0;
        border-title-color: #88C0D0;
        border-title-background: #3B4252;
        padding: 1;
        margin: 1 0;
    }

    .todolist-title {
        width: 100%;
        text-align: center;
        color: #88C0D0;
        text-style: bold;
        margin-bottom: 1;
    }

    .todolist-item {
        width: 100%;
        padding: 0 1;
        margin: 0;
        color: #E5E9F0;
    }

    .todolist-separator {
        width: 100%;
        height: 1;
        background: #4C566A;
        margin: 1 0;
    }

    .todolist-empty {
        width: 100%;
        text-align: center;
        color: #81A1C1;
        padding: 1;
    }
    """

    def __init__(self, todolists: list[TodolistItem]) -> None:
        super().__init__()
        self.todolists = todolists
        self.border_title = "Todolist List"

    def compose(self) -> ComposeResult:
        if not self.todolists:
            yield Static("当前没有todolist。", classes="todolist-empty")
            return

        for i, todolist in enumerate(self.todolists):
            if i > 0:
                yield Static(classes="todolist-separator")
            yield Static(
                f"{todolist['id']}: {todolist['content']}", classes="todolist-item"
            )

    def on_mount(self) -> None:
        self.add_class("todolist-widget")
