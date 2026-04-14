"""TUI UI components for LinHai agent."""

import asyncio
import colorsys
import json
import re
import time
from typing import Union, Optional, Callable, Awaitable

from rich.markup import escape
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import work, events
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Markdown, Static, TextArea
from textual.widgets.markdown import MarkdownBlock

from linhai.sandbox import NoSandbox, ProcessSandboxProtocol
from linhai.streamjson.main import StreamJsonParser, Value, ValuePiece
from linhai.parsed_message import Segment, ParsedAnswer
from linhai.utils.common import parse_and_simplify_toolcall

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
    ".nix": "nix",
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


def _syntax_or_text(content: str, lexer: str, theme: str | None) -> Syntax | Text:
    if theme is not None:
        return Syntax(
            content,
            lexer=lexer,
            theme=theme,
            background_color="#2E3440",
            word_wrap=True,
        )
    return Text(content)


class MarkdownParagraphWithoutNewLine(MarkdownBlock):
    """类似MarkdownParagraph但是删掉了_update_from_block函数，应该只会有性能上的影响"""

    SCOPED_CSS = False
    DEFAULT_CSS = """
    Markdown > MarkdownParagraphWithoutNewLine {
         margin: 0;
    }
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

    def __init__(
        self,
        ascii_art: str,
        small_ascii_art: str,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.ascii_art = ascii_art
        self.small_ascii_art = small_ascii_art
        self.time_index = 0
        self.last_call_time = time.perf_counter()
        self.slow_counter = 0
        self.rainbow_colors: list[Style] = self._generate_rainbow_colors()
        self.get_refresh_interval = get_refresh_interval
        self.timer: Timer | None = None

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
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self._update_animation)

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

    def _get_appropriate_art(self) -> str:
        if self.size.width == 0:
            return self.ascii_art

        lines = self.ascii_art.splitlines()
        if not lines:
            return self.ascii_art

        max_line_length = max(len(line) for line in lines)

        if self.size.width < max_line_length and self.small_ascii_art != self.ascii_art:
            return self.small_ascii_art

        return self.ascii_art

    def _render_ascii_art(self) -> Text:
        """渲染带斜向彩虹渐变色的ASCII艺术"""
        text = Text()
        lines = self._get_appropriate_art().splitlines()
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

    def __init__(
        self, version: str, llm_name: str, get_refresh_interval: Callable[[], float]
    ):
        super().__init__()
        self.version = version
        self.llm_name = llm_name
        self.animation_stage = 0
        self.elapsed_time = 0.0
        self.daily_quote = "/time set 0"
        self.version_info = f"{self.version} | LLM: {self.llm_name}"
        self.get_refresh_interval = get_refresh_interval
        self.timer: Timer | None = None

    def on_mount(self) -> None:
        """组件挂载时启动动画"""
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self._update_animation)

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
        layout: horizontal;
    }
    
    RuntimeMessageWidget .runtime-level {
        width: 4;
    }
    
    RuntimeMessageWidget .runtime-level-info {
        color: #4C566A;
    }
    
    RuntimeMessageWidget .runtime-level-warning {
        color: #EBCB8B;
    }
    
    RuntimeMessageWidget .runtime-level-error {
        color: #BF616A;
    }
    
    RuntimeMessageWidget .runtime-content {
        width: 1fr;
        color: $text-muted;
    }
    """

    def __init__(self, level: str, content: str):
        super().__init__()
        self.level = level
        self.content_str = content

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        yield Static(
            f"\\[{self.level[0]}] ",
            classes=f"runtime-level runtime-level-{self.level.lower()}",
        )
        yield Static(
            self.content_str,
            classes=f"runtime-content runtime-content-{self.level.lower()}",
        )


class _ToolCallCollapseHeader(Static):
    DEFAULT_CSS = """
    _ToolCallCollapseHeader {
        width: 100%;
        color: $accent;
    }
    """

    def __init__(self, collapse_callback: Callable[[], None]):
        super().__init__("▼ 工具")
        self._collapse_callback = collapse_callback

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self._collapse_callback()


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
        border-left: heavy $accent;
    }

    ToolCallWidget.error {
        border-title-color: red;
        border-left: heavy red;
    }
    
    ToolCallWidget.collapsed {
        text-overflow: ellipsis;
        text-wrap: nowrap;
    }
    """

    def __init__(
        self,
        theme: str | None,
        segment: Segment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.theme = theme
        self._segment = segment
        self.json_str = ""
        self.parser = StreamJsonParser()

        self.timer: Timer | None = None

        self.guessed_content_type = ""
        self.current_content = ""
        self.content_before_current_value = ""
        self.current_key = ""
        self.current_value = ""
        self.has_error = False
        self.error_message = ""
        self.is_collapsed = False
        self.collapse_timer: Timer | None = None
        self.get_refresh_interval = get_refresh_interval

        self._markdown_widget: Markdown | None = None
        self._collapse_header: _ToolCallCollapseHeader | None = None
        self.border_title = "tool call"

    def on_mount(self) -> None:
        """组件挂载时开始解析JSON"""
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self.update_display)

    def update_display(self) -> None:
        if self.has_error:
            self.update(
                _syntax_or_text(
                    self.json_str,
                    lexer="markdown",
                    theme=self.theme,
                )
            )
            self.border_title = "tool call (error)"
            self.add_class("error")
            return

        if self._segment["is_finished"] and self.timer:
            self.timer.stop()
            self._start_collapse_timer()

        segment_content = self._segment["content"]
        if segment_content != self.json_str:
            new_content = segment_content.removeprefix(self.json_str)
            self.json_str = segment_content
            try:
                self.parser.feed_string(new_content)
            except RuntimeError as e:
                self.has_error = True
                self.error_message = str(e)
                return

        for value in self.parser:
            if value.index_key != self.current_key:
                self.current_key = value.index_key
                self.content_before_current_value = self.current_content
                self.current_content += f"- {self.current_key}: `"

            if isinstance(value, Value):
                final_value = (
                    value.value
                    if isinstance(value.value, str)
                    else json.dumps(value.value)
                )

                if "\n" in final_value:
                    backticks = "`" * self.get_backtick_count(final_value)
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}:\n\n{backticks}{self.guessed_content_type}\n{final_value}\n{backticks}\n\n"
                    )
                else:
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}: `{final_value}`\n"
                    )

                new_guessed_type = self._guess_content_type(final_value)
                if not self.guessed_content_type or new_guessed_type:
                    self.guessed_content_type = new_guessed_type

                self.current_value = ""

            elif isinstance(value, ValuePiece):
                self.current_value += value.token
                if "\n" in self.current_value:
                    backtick_count = self.get_backtick_count(self.current_value)
                    backticks = "`" * backtick_count
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}:\n\n{backticks}{self.guessed_content_type}\n{self.current_value}\n{backticks}"
                    )
                else:
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}: `{self.current_value}`"
                    )

            self.update(
                _syntax_or_text(
                    self.current_content.strip(),
                    lexer="markdown",
                    theme=self.theme,
                )
            )

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

    def _collapse(self) -> None:
        """折叠widget，显示简化内容"""
        if self.is_collapsed:
            return

        if self._markdown_widget:
            self._markdown_widget.remove()
            self._markdown_widget = None

        if self._collapse_header:
            self._collapse_header.remove()
            self._collapse_header = None

        self.is_collapsed = True
        self.add_class("collapsed")
        self.border_title = "tool call [点击展开]"
        simplified = "<bad toolcall>"
        if not self.has_error:
            simplified = parse_and_simplify_toolcall(self.json_str)
        self.update(
            _syntax_or_text(
                simplified,
                lexer="python",
                theme=self.theme,
            )
        )

    def _expand(self) -> None:
        """展开widget，显示完整内容"""
        if not self.is_collapsed:
            return

        self.is_collapsed = False
        self.remove_class("collapsed")

        if self._segment["is_finished"] and not self.has_error:
            self.border_title = "tool call"
            self.update("")
            self._collapse_header = _ToolCallCollapseHeader(self._collapse)
            self.mount(self._collapse_header)
            self._markdown_widget = Markdown(self.current_content.strip())
            self.mount(self._markdown_widget)
        else:
            self.border_title = "tool call [点击隐藏]"
            self.update(
                _syntax_or_text(
                    self.current_content.strip(),
                    lexer="markdown",
                    theme=self.theme,
                )
            )

    def _start_collapse_timer(self) -> None:
        if self.collapse_timer:
            self.collapse_timer.stop()

        self.collapse_timer = self.set_timer(0.2, self._collapse)

    def on_click(self) -> None:
        """点击事件，切换折叠状态"""
        if self.is_collapsed:
            self._expand()
        elif not self._segment["is_finished"] or self.has_error:
            self._collapse()


class ReasoningContentWidget(Static):
    """思考消息显示组件，不换行并用省略号省略超出行"""

    DEFAULT_CSS = """
    ReasoningContentWidget {
        width: 100%;
        overflow: hidden;
        border-title-color: grey;
        border-title-align: left;
        border-left: heavy grey;
        padding-left: 1;
        padding-right: 1;
        color: $text-muted;
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

    def __init__(
        self,
        role: str,
        sender_name: str,
        theme: str | None,
        segment: Segment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.theme = theme
        self._segment = segment
        self.role = f"{role}-reasoning"
        self.content_str = ""
        self.is_expanded = False
        self.timer: Timer | None = None
        self.sender_name = sender_name
        self.get_refresh_interval = get_refresh_interval
        self.border_title = self.calculate_border_title()
        self.add_class("reasoning-widget-collapsed")

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
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self.update_display)

    def update_display(self) -> None:
        """更新思考消息显示"""
        if self._segment["is_finished"] and self.timer:
            self.timer.stop()

        segment_content = self._segment["content"]
        if segment_content != self.content_str:
            self.content_str = segment_content

        content_to_display = self.content_str.strip()

        if self.is_expanded:
            renderable = _syntax_or_text(
                content_to_display,
                lexer="markdown",
                theme=self.theme,
            )
        else:
            lines = [line for line in content_to_display.splitlines() if line]
            truncated_content = "\n".join(lines[-2:]) if lines else ""
            renderable = Text(truncated_content, overflow="ellipsis", no_wrap=True)

        self.update(renderable)


class UserMessageWidget(Markdown):
    """用户消息显示组件"""

    SCOPED_CSS = False
    DEFAULT_CSS = """
    UserMessageWidget {
        width: 100%;
        overflow: hidden;
        padding-left: 1;
        padding-right: 1;
        border-title-align: left;
        border-title-color: #A3BE8C;
        border-left: heavy #A3BE8C;
    }
    """

    def get_block_class(self, block_name: str) -> type[MarkdownBlock]:
        """去除每个消息后的空行"""
        if block_name == "paragraph_open":
            return MarkdownParagraphWithoutNewLine
        return Markdown.BLOCKS[block_name]

    def __init__(self, content: str, sender_name: str, theme: str | None):
        super().__init__()
        self.theme = theme
        self.content_str = content
        self.display_name = sender_name
        self.timer: Timer | None = None
        self.border_title = self.display_name

    def on_mount(self) -> None:
        """组件挂载时开始显示"""
        self.update_display()

    def update_display(self) -> None:
        """更新普通消息显示，按字符换行"""
        content_to_display = self.content_str.strip()
        self.update(content_to_display)


class SpaceWidget(Static):
    """隔开两个消息的空消息"""

    DEFAULT_CSS = """
    SpaceWidget {
        width: 100%;
        border-left: heavy $background-lighten-2;
    }
    """


class NormalContentWidget(Markdown):
    """普通消息显示组件，按字符换行"""

    DEFAULT_CSS = """
    NormalContentWidget {
        width: 100%;
        overflow: hidden;
        padding-left: 1;
        padding-right: 1;
        border-title-align: left;
        border-title-color: $primary;
        border-left: heavy $primary;
    }
    """

    def __init__(
        self,
        role: str,
        sender_name: str,
        theme: str | None,
        segment: Segment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.theme = theme
        self.content_str = ""
        self.display_name = sender_name
        self.role = role
        self.timer = None
        self._segment = segment
        self.get_refresh_interval = get_refresh_interval
        self.add_class(f"{self.role}-message")
        self.border_title = self.display_name

    def get_block_class(self, block_name: str) -> type[MarkdownBlock]:
        """去除每个消息后的空行"""
        if block_name == "paragraph_open":
            return MarkdownParagraphWithoutNewLine
        return Markdown.BLOCKS[block_name]

    def on_mount(self) -> None:
        """组件挂载时开始显示"""
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self.update_display)

    def update_display(self) -> None:
        """更新普通消息显示，按字符换行"""
        if self._segment["is_finished"] and self.timer:
            self.timer.stop()

        segment_content = self._segment["content"]
        if segment_content != self.content_str:
            self.content_str = segment_content

        content_to_display = self.content_str.strip()

        self.update(content_to_display)

    def content_is_empty(self) -> bool:
        """检查内容是否为空或只包含空白字符"""
        return not self.content_str.strip()

    def stop_timer(self) -> None:
        """停止timer，防止删除后继续更新"""
        if self.timer:
            self.timer.stop()


class MessageWidget(Static):
    """消息显示组件，支持ParsedAnswer和segment流式显示"""

    DEFAULT_CSS = """
    MessageWidget {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        role: str,
        sender_name: str,
        theme: str | None,
        parsed_answer: ParsedAnswer,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.role = role
        self.sender_name = sender_name
        self.theme = theme
        self.parsed_answer = parsed_answer
        self.get_refresh_interval = get_refresh_interval

    def on_mount(self):
        self._start_processing_segments()

    @work(exclusive=False)
    async def _start_processing_segments(self):
        is_first_segment = True
        last_content_widget = None
        while True:
            segment = await self.parsed_answer.segment_queue.get()

            if not is_first_segment:
                if (
                    isinstance(last_content_widget, NormalContentWidget)
                    and last_content_widget.content_is_empty()
                ):
                    last_content_widget.stop_timer()
                    last_content_widget.remove()
                else:
                    self.mount(SpaceWidget())

            segment_type = segment["segment_type"]
            if segment_type == "toolcall":
                widget = ToolCallWidget(
                    theme=self.theme,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment_type == "normal":
                widget = NormalContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    theme=self.theme,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment_type == "reasoning":
                widget = ReasoningContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    theme=self.theme,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            else:
                continue

            self.mount(widget)
            last_content_widget = widget
            is_first_segment = False

    def finish_streaming(self) -> None:
        """停止所有widget的timer"""


class FooterWidget(Static):
    """底栏组件，自动刷新显示token和消息统计信息"""

    DEFAULT_CSS = """
    FooterWidget {
        background: $background-darken-1;
        color: $foreground-darken-3;
    }
    """

    def __init__(self, registry, token_manager, use_nerd_font=False):
        super().__init__("")
        self.registry = registry
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

    def _get_current_llm_name(self) -> str:
        """获取当前LLM名称"""
        from linhai.agent import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm_name, _ = agent.get_current_llm_info(rotate_invalid_llm=False)
        return llm_name

    def update_display(self):
        """
        更新底栏显示内容。

        自动获取当前token用量和消息统计信息，并在没有token信息时显示默认消息。
        优化刷新逻辑，只在需要时更新显示。
        """
        from linhai.agent import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)

        token_pieces = self.token_manager.get_token_display_pieces(
            agent, self.current_answer_token, self.use_nerd_font
        )

        sandbox = self.registry.get_member_typechecked(
            "process_sandbox", ProcessSandboxProtocol
        )
        if not isinstance(sandbox, NoSandbox):
            sandbox_icon = "\uf132" if self.use_nerd_font else "◭"
            token_pieces.append(sandbox_icon)

        llm_name = self._get_current_llm_name()
        if self.use_nerd_font:
            llm_piece = b"\xf3\xb0\xab\xa2".decode() + f" {llm_name}"
        else:
            llm_piece = f"✦ {llm_name}"
        all_pieces = token_pieces + [llm_piece]
        display_text = " | ".join(all_pieces)

        self.update(display_text)


class MessageGenerationWidget(Static):
    DEFAULT_CSS = """
    MessageGenerationWidget {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.tomount: Optional[list] = []

    def set_message_widget(self, widget: MessageWidget) -> None:
        if self.tomount is not None:
            self.tomount.append(widget)
        else:
            self.mount(widget)

    def add_runtime_message(self, widget: RuntimeMessageWidget) -> None:
        if self.tomount is not None:
            self.tomount.append(widget)
        else:
            self.mount(widget)

    def on_mount(self):
        if self.tomount is not None:
            for widget in self.tomount:
                self.mount(widget)
        self.tomount = None


class ExtendedTextArea(TextArea):
    """A subclass of TextArea with parenthesis-closing functionality."""

    def __init__(self, on_enter_key: Callable[[], Awaitable], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_enter_key = on_enter_key

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            await self.on_enter_key()
            event.stop()
        if event.key == "shift+enter":
            self.insert("\n")
            event.stop()
