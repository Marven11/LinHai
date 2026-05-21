"""TUI UI components for LinHai agent."""

import colorsys
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
from textual.widgets._markdown import MarkdownStream
from textual.widgets.markdown import MarkdownBlock

from linhai.sandbox import NoSandbox, ProcessSandboxProtocol
from linhai.utils.i18n import t
from linhai.parsed_message import (
    ToolCallSegment,
    OpenAiToolCallSegment,
    NormalSegment,
    ReasoningSegment,
    ParsedAnswer,
)
from linhai.utils.common import (
    parse_and_simplify_toolcall,
    cluster_tool_calls,
    BAD_TOOLCALL,
)

StoppableWidget = Union[
    "ToolCallWidget", "NormalContentWidget", "ReasoningContentWidget"
]


def _simplify_openai_toolcall(tool_name: str, raw: str) -> str:
    full_json = f'{{"name":"{tool_name}","arguments":{raw}}}'
    return parse_and_simplify_toolcall(full_json)


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
            markup=False,
        )
        yield Static(
            self.content_str,
            classes=f"runtime-content runtime-content-{self.level.lower()}",
            markup=False,
        )


class _ClickStatic(Static):
    DEFAULT_CSS = """
    _ClickStatic {
        width: 100%;
        color: $text-muted;
        padding-left: 1;
        border-left: heavy $background-lighten-2;
    }
    """

    def __init__(self, content: str, on_click_fn: Callable[[], None]):
        super().__init__(content)
        self._on_click_fn = on_click_fn

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self._on_click_fn()


class _ToolCallCollapseHeader(Static):
    DEFAULT_CSS = """
    _ToolCallCollapseHeader {
        width: 100%;
        color: $accent;
    }
    """

    def __init__(self, collapse_callback: Callable[[], None]):
        super().__init__(t({"zh_CN": "▼ 工具", "en": "▼ Tool"}))
        self._collapse_callback = collapse_callback

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self._collapse_callback()


class ToolCallWidget(Static):
    """工具调用显示组件，从ToolCallSegment读取已解析的markdown表示"""

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
        pygments_theme: str,
        syntax_background: str | None,
        segment: ToolCallSegment | OpenAiToolCallSegment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.pygments_theme = pygments_theme
        self.syntax_background = syntax_background
        self._segment = segment
        self._last_rendered = ""
        self.is_collapsed = False
        self.collapse_timer: Timer | None = None
        self.get_refresh_interval = get_refresh_interval
        self.timer: Timer | None = None
        self._markdown_widget: Markdown | None = None
        self._collapse_header: _ToolCallCollapseHeader | None = None
        self.border_title = "tool call"

    def on_mount(self) -> None:
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self.update_display)

    @property
    def has_error(self) -> bool:
        return self._segment["is_corrupted"]

    @property
    def tool_name(self) -> str:
        return self._segment["tool_name"]

    def update_display(self) -> None:
        if self._segment["is_corrupted"]:
            self.update(
                Syntax(
                    self._segment["markdown_representation"],
                    lexer="markdown",
                    theme=self.pygments_theme,
                    background_color=self.syntax_background,
                    word_wrap=True,
                )
            )
            self.border_title = "tool call (error)"
            self.add_class("error")
            return

        if self._segment["is_finished"] and self.timer:
            self.timer.stop()
            self._start_collapse_timer()

        md = self._segment["markdown_representation"]
        if md != self._last_rendered:
            self._last_rendered = md
            self.update(
                Syntax(
                    md,
                    lexer="markdown",
                    theme=self.pygments_theme,
                    background_color=self.syntax_background,
                    word_wrap=True,
                )
            )

    def _collapse(self) -> None:
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
        self.border_title = t(
            {"zh_CN": "tool call [点击展开]", "en": "tool call [click to expand]"}
        )
        simplified = BAD_TOOLCALL
        if not self._segment["is_corrupted"]:
            if self._segment["segment_type"] == "openai_toolcall":
                tool_name = self._segment["tool_name"] or "unknown"
                simplified = _simplify_openai_toolcall(tool_name, self._segment["raw"])
            else:
                simplified = parse_and_simplify_toolcall(self._segment["raw"])
        self.update(
            Syntax(
                simplified,
                lexer="python",
                theme=self.pygments_theme,
                background_color=self.syntax_background,
                word_wrap=True,
            )
        )

    def _expand(self) -> None:
        if not self.is_collapsed:
            return

        self.is_collapsed = False
        self.remove_class("collapsed")

        if self._segment["is_finished"] and not self._segment["is_corrupted"]:
            self.border_title = "tool call"
            self.update("")
            self._collapse_header = _ToolCallCollapseHeader(self._collapse)
            self.mount(self._collapse_header)
            self._markdown_widget = Markdown(self._segment["markdown_representation"])
            self.mount(self._markdown_widget)
        else:
            self.border_title = t(
                {"zh_CN": "tool call [点击隐藏]", "en": "tool call [click to hide]"}
            )
            self.update(
                Syntax(
                    self._segment["markdown_representation"],
                    lexer="markdown",
                    theme=self.pygments_theme,
                    background_color=self.syntax_background,
                    word_wrap=True,
                )
            )

    def _start_collapse_timer(self) -> None:
        if self.collapse_timer:
            self.collapse_timer.stop()

        self.collapse_timer = self.set_timer(0.2, self._collapse)

    def on_click(self) -> None:
        if self.is_collapsed:
            self._expand()
        elif not self._segment["is_finished"] or self._segment["is_corrupted"]:
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
        pygments_theme: str,
        syntax_background: str | None,
        segment: ReasoningSegment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.pygments_theme = pygments_theme
        self.syntax_background = syntax_background
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
        toggle = (
            t({"zh_CN": "[点击隐藏]", "en": "[click to hide]"})
            if self.is_expanded
            else t({"zh_CN": "[点击展开]", "en": "[click to expand]"})
        )
        return f"{self.sender_name} (reasoning) {toggle}"

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
            renderable = Syntax(
                content_to_display,
                lexer="markdown",
                theme=self.pygments_theme,
                background_color=self.syntax_background,
                word_wrap=True,
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

    def __init__(self, content: str, sender_name: str, pygments_theme: str):
        super().__init__()
        self.pygments_theme = pygments_theme
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
        pygments_theme: str,
        segment: NormalSegment,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.pygments_theme = pygments_theme
        self.display_name = sender_name
        self.role = role
        self.timer: Timer | None = None
        self._segment = segment
        self.get_refresh_interval = get_refresh_interval
        self._stream: MarkdownStream | None = None
        self._streamed_content = ""
        self.add_class(f"{self.role}-message")
        self.border_title = self.display_name

    def get_block_class(self, block_name: str) -> type[MarkdownBlock]:
        """去除每个消息后的空行"""
        if block_name == "paragraph_open":
            return MarkdownParagraphWithoutNewLine
        return Markdown.BLOCKS[block_name]

    def on_mount(self) -> None:
        """组件挂载时开始流式显示"""
        self._stream = Markdown.get_stream(self)
        refresh_interval = self.get_refresh_interval()
        self.timer = self.set_interval(refresh_interval, self.update_display)

    async def update_display(self) -> None:
        """增量更新普通消息显示"""
        segment_content = self._segment["content"]

        if segment_content != self._streamed_content:
            new_content = segment_content.removeprefix(self._streamed_content)
            self._streamed_content = segment_content

            if self._segment["is_finished"]:
                if self._stream is not None:
                    await self._stream.stop()
                    self._stream = None
                self.update(segment_content.strip())
                if self.timer:
                    self.timer.stop()
            elif new_content and self._stream is not None:
                await self._stream.write(new_content)
        elif self._segment["is_finished"] and self.timer:
            if self._stream is not None:
                await self._stream.stop()
                self._stream = None
            self.update(segment_content.strip())
            if self.timer:
                self.timer.stop()

    def content_is_empty(self) -> bool:
        """检查内容是否为空或只包含空白字符"""
        return not self._streamed_content.strip()

    async def on_unmount(self) -> None:
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self._stream is not None:
            await self._stream.stop()
            self._stream = None

    def stop_timer(self) -> None:
        """停止timer，防止删除后继续更新"""
        if self.timer:
            self.timer.stop()


class MessageWidget(Static):
    DEFAULT_CSS = """
    MessageWidget.has-runtime-message {
        margin-bottom: 1;
    }
    MessageWidget .message-segments {
        width: 100%;
    }
    """

    def __init__(
        self,
        role: str,
        sender_name: str,
        pygments_theme: str,
        syntax_background: str | None,
        parsed_answer: ParsedAnswer | None,
        get_refresh_interval: Callable[[], float],
    ):
        super().__init__()
        self.role = role
        self.sender_name = sender_name
        self.pygments_theme = pygments_theme
        self.syntax_background = syntax_background
        self.parsed_answer = parsed_answer
        self.get_refresh_interval = get_refresh_interval
        self._restored_segments: list[dict] | None = None
        self._state = "streaming"
        self._collapsed_view = _ClickStatic("\u25b6", self._expand_message)
        self._expand_header = _ClickStatic(
            "\u25bc",
            self._collapse_message,
        )
        self._content = Static(classes="message-segments")
        self._collapsed_view.display = False
        self._expand_header.display = False
        self._auto_transition_timer: Timer | None = None
        self._streaming_timer: Timer | None = None

    def on_mount(self):
        self.mount(self._collapsed_view)
        self.mount(self._expand_header)
        self.mount(self._content)
        if self._restored_segments is not None:
            self._restore_segments(self._restored_segments)
        else:
            self._start_processing_segments()
        self._streaming_timer = self.set_interval(
            self.get_refresh_interval(), self._update_streaming_header
        )

    def _restore_segments(self, segments: list[dict]) -> None:
        for i, segment_data in enumerate(segments):
            if i > 0:
                self._content.mount(SpaceWidget())
            segment_type = segment_data["segment_type"]
            if segment_type in ("toolcall", "openai_toolcall"):
                if segment_type == "toolcall":
                    seg = ToolCallSegment(
                        segment_type="toolcall",
                        raw=segment_data["raw"],
                        is_finished=segment_data["is_finished"],
                        is_corrupted=segment_data["is_corrupted"],
                        markdown_representation=segment_data["markdown_representation"],
                        tool_name=segment_data["tool_name"],
                    )
                else:
                    seg = OpenAiToolCallSegment(
                        segment_type="openai_toolcall",
                        idx=segment_data["idx"],
                        id=segment_data["id"],
                        raw=segment_data["raw"],
                        is_finished=segment_data["is_finished"],
                        is_corrupted=segment_data["is_corrupted"],
                        markdown_representation=segment_data["markdown_representation"],
                        tool_name=segment_data["tool_name"],
                    )
                widget = ToolCallWidget(
                    pygments_theme=self.pygments_theme,
                    syntax_background=self.syntax_background,
                    segment=seg,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment_type == "normal":
                seg = NormalSegment(
                    segment_type="normal",
                    content=segment_data["content"],
                    is_finished=segment_data["is_finished"],
                )
                widget = NormalContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    pygments_theme=self.pygments_theme,
                    segment=seg,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment_type == "reasoning":
                seg = ReasoningSegment(
                    segment_type="reasoning",
                    content=segment_data["content"],
                    is_finished=segment_data["is_finished"],
                )
                widget = ReasoningContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    pygments_theme=self.pygments_theme,
                    syntax_background=self.syntax_background,
                    segment=seg,
                    get_refresh_interval=self.get_refresh_interval,
                )
            else:
                continue
            self._content.mount(widget)
        self._auto_transition()

    @work(exclusive=False)
    async def _start_processing_segments(self):
        assert self.parsed_answer is not None
        is_first_segment = True
        last_content_widget = None
        while True:
            segment = await self.parsed_answer.segment_queue.get()

            if segment is None:
                self._schedule_auto_transition()
                break

            if not is_first_segment:
                if (
                    isinstance(last_content_widget, NormalContentWidget)
                    and last_content_widget.content_is_empty()
                ):
                    last_content_widget.stop_timer()
                    last_content_widget.remove()
                else:
                    self._content.mount(SpaceWidget())

            if (
                segment["segment_type"] == "toolcall"
                or segment["segment_type"] == "openai_toolcall"
            ):
                widget = ToolCallWidget(
                    pygments_theme=self.pygments_theme,
                    syntax_background=self.syntax_background,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment["segment_type"] == "normal":
                widget = NormalContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    pygments_theme=self.pygments_theme,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            elif segment["segment_type"] == "reasoning":
                widget = ReasoningContentWidget(
                    role=self.role,
                    sender_name=self.sender_name,
                    pygments_theme=self.pygments_theme,
                    syntax_background=self.syntax_background,
                    segment=segment,
                    get_refresh_interval=self.get_refresh_interval,
                )
            else:
                continue

            self._content.mount(widget)
            last_content_widget = widget
            is_first_segment = False
            if self._state == "collapsed":
                summary = self._get_collapsed_summary()
                self._collapsed_view.update(summary)

    def _schedule_auto_transition(self) -> None:
        self._auto_transition_timer = self.set_timer(1.0, self._auto_transition)

    def _auto_transition(self) -> None:
        has_tool_calls = any(
            isinstance(w, ToolCallWidget) for w in self._content.children
        )
        if has_tool_calls:
            self._collapse_message()
        else:
            self._state = "expanded"

    @staticmethod
    def _shorten_collapsed_content(content: str) -> str:
        if "\n" in content or len(content) > 40:
            content = content.replace("\n", " ").replace("\r", " ")
            if len(content) > 40:
                return content[:20] + "..." + content[-20:]
        return content

    def _get_collapsed_summary(self) -> Text:
        parts: list[str | list[str]] = []
        pending_tools: list[str] = []
        for child in self._content.children:
            if isinstance(child, ToolCallWidget):
                if child.has_error:
                    pending_tools.append(BAD_TOOLCALL)
                else:
                    pending_tools.append(child.tool_name or "unknown")
            elif isinstance(child, NormalContentWidget):
                if pending_tools:
                    parts.append(pending_tools)
                    pending_tools = []
                content = child._streamed_content.strip()
                if content:
                    parts.append(self._shorten_collapsed_content(content))
        if pending_tools:
            parts.append(pending_tools)

        text = Text("\u25b6 ")
        for part in parts:
            if isinstance(part, list):
                if len(text.plain) > 2:
                    text.append(" ")
                clusters = cluster_tool_calls(part)
                text.append("[")
                for j, (name, count) in enumerate(clusters):
                    if j > 0:
                        text.append(", ")
                    text.append(name, style=Style(bold=True))
                    if count > 1:
                        text.append(f"*{count}")
                text.append("]")
            else:
                text.append(part)
        return text

    def _get_expand_header_text(self) -> Text:
        tool_names: list[str] = []
        for child in self._content.children:
            if isinstance(child, ToolCallWidget):
                if child._segment["is_finished"] and not child.has_error:
                    tool_names.append(child.tool_name or "unknown")
        clusters = cluster_tool_calls(tool_names)
        text = Text("\u25bc ")
        for i, (name, count) in enumerate(clusters):
            if i > 0:
                text.append(", ")
            text.append(name, style=Style(bold=True))
            if count > 1:
                text.append(f"*{count}")
        return text

    def _update_streaming_header(self) -> None:
        if self._state != "streaming":
            if self._streaming_timer:
                self._streaming_timer.stop()
                self._streaming_timer = None
            return
        header_text = self._get_expand_header_text()
        if len(header_text.plain) > 2:
            self._expand_header.update(header_text)
            self._expand_header.display = True
        else:
            self._expand_header.display = False

    def _collapse_message(self) -> None:
        if self._state == "collapsed":
            return
        self._state = "collapsed"
        summary = self._get_collapsed_summary()
        self._collapsed_view.update(summary)
        self._collapsed_view.display = True
        self._expand_header.display = False
        self._content.display = False

    def _expand_message(self) -> None:
        if self._state == "expanded":
            return
        self._state = "expanded"
        self._collapsed_view.display = False
        header_text = self._get_expand_header_text()
        self._expand_header.update(header_text)
        self._expand_header.display = True
        self._content.display = True

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
        if isinstance(sandbox, NoSandbox):
            sandbox_icon = "\uf530" if self.use_nerd_font else "\u2716"
        else:
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
        self._has_runtime_message = False

    def set_message_widget(self, widget: MessageWidget) -> None:
        if self.tomount is not None:
            self.tomount.append(widget)
        else:
            self.mount(widget)

    def add_runtime_message(self, widget: RuntimeMessageWidget) -> None:
        self._has_runtime_message = True
        if self.tomount is not None:
            self.tomount.append(widget)
        else:
            self.mount(widget)
            self._apply_runtime_class()

    def on_mount(self):
        if self.tomount is not None:
            for widget in self.tomount:
                self.mount(widget)
        self.tomount = None
        if self._has_runtime_message:
            self._apply_runtime_class()

    def _apply_runtime_class(self) -> None:
        for child in self.children:
            if isinstance(child, MessageWidget):
                child.add_class("has-runtime-message")
                break


class CommandCompletionMenu(Static):
    DEFAULT_CSS = """
    CommandCompletionMenu {
        display: none;
        width: 100%;
        height: auto;
        max-height: 10;
        background: $surface;
        border: tall $accent;
        padding: 0 1;
        overflow: hidden auto;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.candidates: list[str] = []
        self.selected_index: int = 0
        self.is_visible: bool = False

    def update_candidates(self, _prefix: str, candidates: list[str]) -> None:
        if not candidates:
            self.hide_menu()
            return
        self.candidates = candidates[:8]
        self.selected_index = min(self.selected_index, len(self.candidates) - 1)
        self.is_visible = True
        self.display = True
        self._render_candidates()

    def hide_menu(self) -> None:
        self.display = False
        self.is_visible = False
        self.candidates = []

    def select_up(self) -> None:
        if self.candidates:
            self.selected_index = (self.selected_index - 1) % len(self.candidates)
            self._render_candidates()

    def select_down(self) -> None:
        if self.candidates:
            self.selected_index = (self.selected_index + 1) % len(self.candidates)
            self._render_candidates()

    def get_selected(self) -> str | None:
        if 0 <= self.selected_index < len(self.candidates):
            return self.candidates[self.selected_index]
        return None

    def _render_candidates(self) -> None:
        text = Text()
        for i, candidate in enumerate(self.candidates):
            if i > 0:
                text.append("\n")
            if i == self.selected_index:
                text.append(f" {candidate}", style=Style(reverse=True, bold=True))
            else:
                text.append(f" {candidate}")
        self.update(text)


class ExtendedTextArea(TextArea):

    def __init__(
        self,
        on_enter_key: Callable[[], Awaitable],
        get_command_completions: Callable[[], list[str]],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.on_enter_key = on_enter_key
        self.get_command_completions = get_command_completions
        self._completion_timer: Timer | None = None

    def _get_completion_menu(self) -> CommandCompletionMenu | None:
        results = self.app.query("#completion-menu")
        for widget in results:
            if isinstance(widget, CommandCompletionMenu):
                return widget
        return None

    def _find_command_prefix(self) -> tuple[str, int, int] | None:
        row, col = self.cursor_location
        line = self.document.get_line(row)
        text_before = line[:col]
        slash_idx = text_before.rfind("/")
        if slash_idx == -1:
            return None
        if slash_idx > 0 and text_before[slash_idx - 1] not in (" ", "\t"):
            return None
        return text_before[slash_idx:], slash_idx, row

    def _update_completion(self) -> None:
        menu = self._get_completion_menu()
        if menu is None:
            return
        result = self._find_command_prefix()
        if result is None:
            if menu.is_visible:
                menu.hide_menu()
            return
        prefix, _, _ = result
        commands = self.get_command_completions()
        matches = [c for c in commands if c.startswith(prefix)]
        if not matches or (len(matches) == 1 and matches[0] == prefix):
            menu.hide_menu()
        else:
            menu.update_candidates(prefix, matches)

    def _complete_command(self) -> None:
        menu = self._get_completion_menu()
        if menu is None or not menu.is_visible:
            return
        selected = menu.get_selected()
        if selected is None:
            return
        result = self._find_command_prefix()
        if result is None:
            return
        _prefix, slash_col, row = result
        _, col = self.cursor_location
        line = self.document.get_line(row)
        after_cursor = line[col:]
        replacement = selected
        if not (after_cursor and after_cursor[0] == " "):
            replacement += " "
        new_line = line[:slash_col] + replacement + after_cursor
        new_col = slash_col + len(replacement)
        all_lines = self.text.split("\n")
        all_lines[row] = new_line
        self.text = "\n".join(all_lines)
        self.move_cursor((row, new_col))
        menu.hide_menu()

    def _schedule_update(self) -> None:
        if self._completion_timer is not None:
            self._completion_timer.stop()
        self._completion_timer = self.set_timer(0.05, self._update_completion)

    def action_cursor_up(self, select: bool = False) -> None:
        menu = self._get_completion_menu()
        if menu is not None and menu.is_visible:
            menu.select_up()
        else:
            super().action_cursor_up(select=select)

    def action_cursor_down(self, select: bool = False) -> None:
        menu = self._get_completion_menu()
        if menu is not None and menu.is_visible:
            menu.select_down()
        else:
            super().action_cursor_down(select=select)

    async def _on_key(self, event: events.Key) -> None:
        menu = self._get_completion_menu()
        is_visible = menu is not None and menu.is_visible

        if event.key == "enter":
            if menu:
                menu.hide_menu()
            await self.on_enter_key()
            event.stop()
            return

        if event.key == "shift+enter":
            self.insert("\n")
            event.stop()
            self._schedule_update()
            return

        if is_visible:
            if event.key == "tab":
                self._complete_command()
                event.stop()
                return
            if event.key == "escape":
                if menu is not None:
                    menu.hide_menu()
                event.stop()
                return

        self._schedule_update()
