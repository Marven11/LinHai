"""CLI UI components for LinHai agent."""

import time
import colorsys
from typing import Optional

from textual.app import ComposeResult
from textual.widgets import Static
from textual.timer import Timer
from rich import box
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.table import Table
from linhai.llm import ChatMessage
from linhai.streamjson.main import StreamJsonParser, Value, ValuePiece

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

    def __init__(self, ascii_art: str):
        super().__init__()
        self.ascii_art = ascii_art
        self.time_index = 0
        self.last_call_time = time.perf_counter()
        self.slow_counter = 0
        self.rainbow_colors: list[Style] = self._generate_rainbow_colors()

    def _generate_rainbow_colors(self) -> list[Style]:
        """使用HSL颜色空间生成平滑的彩虹颜色样式列表"""
        import colorsys

        num_colors = 256
        styles = []
        for i in range(num_colors):
            # 色相从0到1循环，对应彩虹颜色
            hue = i / num_colors
            rgb = colorsys.hls_to_rgb(hue, 0.5, 0.8)
            # 将RGB值从0-1范围转换为0-255范围
            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)
            styles.append(Style(color=f"rgb({r},{g},{b})"))
        mid = len(styles) // 2
        styles = styles[mid:] + styles[:mid]
        return styles

    def on_mount(self) -> None:
        """组件挂载时启动动画"""
        self.set_interval(0.1, self._update_animation)

    def _update_animation(self) -> None:
        """更新动画时间索引并重新渲染"""
        self.time_index += 1

        # if it is slow for whatever reason, stop
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
                # 计算颜色索引：斜向渐变，使用 (row + col + time_index) % len(rainbow_colors)
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

    def __init__(self, version: str, llm_name: str):
        super().__init__()
        self.version = version
        self.llm_name = llm_name
        self.animation_stage = 0  # 0: 每日一言, 1: 乱码, 2: 版本信息
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
        if self.animation_stage == 0:  # 每日一言阶段

            self.update(self._render_daily_quote())
        elif self.animation_stage == 1:  # 乱码阶段
            self.update(self._render_glitch())
        else:  # 版本信息阶段
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
        import colorsys

        text = Text()
        glitch_text = "".join(
            random.choice("!@#$%^&*()_+-=[]{}|;:,.<>?/~`")
            for _ in range(max(len(self.daily_quote), len(self.version_info)))
        )
        # 从0.2 ~ 1.2秒
        saturation = max(0, 1.2 - self.elapsed_time)
        lightness = 0.5
        hue = 50.59 / 360

        # 将HSL转换为RGB
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

    def __init__(self, level: str, content: str):
        super().__init__()
        self.level = level
        self.content = content

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        # 设置样式
        level_style = {"INFO": "grey50", "WARNING": "yellow", "ERROR": "red"}.get(
            self.level, "grey50"
        )

        # 创建消息文本
        message_text = Text()
        message_text.append(f"[{self.level[0]}]", style=level_style)
        message_text.append(f" {self.content}")

        yield Static(message_text)


class CandidateList(Static):
    """候选列表组件，用于显示补全选项"""

    def __init__(self, candidates: list[str], prefix: str):
        super().__init__()
        self.candidates = candidates
        self.prefix = prefix
        self.selected_index = 0

    def on_mount(self) -> None:
        """组件挂载时更新显示"""
        self.update_display()

    def update_display(self) -> None:
        """更新显示"""
        # 显示候选列表，底部最靠近文本框的是最有可能的候选项（索引0）
        # 列表没有边框
        text = Text()
        candidates = list(reversed(list(enumerate(self.candidates))))
        for i, candidate in candidates:
            # 计算显示位置：索引0显示在底部，索引n-1显示在顶部
            if i == self.selected_index:
                text.append(f"> {self.prefix}{candidate}", style="reverse")
            else:
                text.append(f"  {self.prefix}{candidate}")
            # 如果不是最后一个候选项，添加换行符
            if i != 0:
                text.append("\n")
        self.update(text)

    def update_selection(self, direction: int):
        """更新选择"""
        self.selected_index = (self.selected_index + direction) % len(self.candidates)
        self.update_display()

    def get_selected(self) -> str:
        """获取当前选中的候选项"""
        return self.candidates[self.selected_index]


class ToolCallWidget(Static):
    """工具调用显示组件，流式显示键值对表格"""

    def __init__(self, json_str: str):
        super().__init__()
        self.json_str = json_str
        self.parser = StreamJsonParser()

        self.guessed_content_type = ""
        self.current_content = ""
        self.content_before_current_value = ""
        self.current_key = ""
        self.current_value = ""

    def feed_string(self, s: str):
        self.parser.feed_string(s)

    def is_current_data_finished(self):
        return self.parser.is_current_data_finished()

    def on_mount(self) -> None:
        """组件挂载时开始解析JSON"""
        self.set_interval(0.05, self._update_display)
        # 喂入JSON字符串到解析器
        self.parser.feed_string(self.json_str)

    def _update_display(self) -> None:
        """更新显示"""
        # 从解析器获取新的值
        for value in self.parser:
            if value.index_key != self.current_key:
                self.current_key = value.index_key
                self.content_before_current_value = self.current_content
                self.current_content += f"- {self.current_key}: `"

            if isinstance(value, Value):
                final_value = str(value.value)
                if "\n" in final_value:
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}:\n\n```{self.guessed_content_type}\n{final_value}\n```\n\n"
                    )
                else:
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}: `{final_value}`\n"
                    )


                # [TODO] 添加常用格式，包括热门编程语言和markdown, json, html等常用纯文本格式
                if final_value.endswith(".py"):
                    self.guessed_content_type = "python"
                if final_value.endswith(".js"):
                    self.guessed_content_type = "javascript"


            elif isinstance(value, ValuePiece):
                self.current_content += value.char
                self.current_value += value.char
                if value.char == "\n":
                    self.current_content = (
                        self.content_before_current_value
                        + f"- {self.current_key}:\n\n```{self.guessed_content_type}\n{self.current_value}"
                    )

            panel = Panel(
                Syntax(
                    self.current_content.strip(),
                    "markdown",
                    theme="nord-darker",
                    background_color="#2E3440",
                    word_wrap=True,
                ),
                box=box.SQUARE,
                border_style="blue",
                title="tool call",
                title_align="left",
                expand=True,
                style="on #2E3440",
            )
            self.update(panel)


class MessageWidget(Static):
    """单条消息显示组件，支持流式token处理和JSON工具调用显示"""

    def __init__(
        self, role: str, content: str, sender_name: str, is_reasoning: bool = False
    ):
        super().__init__()
        self.content_str = content
        self.is_reasoning = is_reasoning
        if is_reasoning:
            self.display_name = f"{sender_name} (reasoning)"
            self.role = f"{role}-reasoning"
        else:
            self.display_name = sender_name
            self.role = role
        self.last_update_time = time.perf_counter()

        self.current_widget: ToolCallWidget | Static | None = None
        self.should_remove_quote = False  # 是否应该去除开头的```
        self.panel_content = content  # 当前普通面板内容

    def update_display(self):
        self.append_content("")

    def append_content(self, new_content: str):
        """流式追加内容到消息，根据内容类型分发到子widget"""
        self.content_str += new_content
        self.panel_content += new_content

        if self.panel_content.endswith("```json toolcall") and not self.is_reasoning:
            self.panel_content = self.panel_content.split("```json toolcall")[0].strip()
            self._update_panel()
            toolcall_widget = ToolCallWidget("")
            self.current_widget = toolcall_widget
            self.mount(toolcall_widget)
        elif isinstance(self.current_widget, ToolCallWidget):
            self.current_widget.feed_string(new_content)
            if self.current_widget.is_current_data_finished():
                self.current_widget = None
                self.should_remove_quote = True
                self.panel_content = ""
        else:
            if self.should_remove_quote:
                if self.panel_content.startswith("```"):
                    self.panel_content = self.panel_content.removeprefix("```")
                    self.should_remove_quote = False
            else:
                self._update_panel()

    def _update_panel(self) -> None:
        """更新普通面板显示"""
        assert not isinstance(self.current_widget, ToolCallWidget)
        if self.panel_content.strip():
            if self.current_widget is None:
                self.current_widget = Static()
                self.mount(self.current_widget)

            # 更新面板内容
            border_color = {
                "user": "yellow",
                "assistant": "green",
                "assistant-reasoning": "grey50",
            }.get(self.role, "grey50")

            content_to_display = self.panel_content
            if self.is_reasoning:
                # 只显示思考内容的最后5行
                lines = content_to_display.splitlines()
                if len(lines) > 5:
                    content_to_display = "\n".join(lines[-5:])

            panel = Panel(
                Syntax(
                    content_to_display,
                    "markdown",
                    theme="nord-darker",
                    background_color="#2E3440",
                    word_wrap=True,
                ),
                box=box.SQUARE,
                border_style=border_color,
                title=self.display_name,
                title_align="left",
                expand=True,
                style="on #2E3440",
            )
            self.current_widget.update(panel)

    def to_message(self) -> ChatMessage:
        """转换为ChatMessage"""
        return ChatMessage(role=self.role, message=self.content_str)
