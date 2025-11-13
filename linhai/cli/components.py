"""CLI UI components for LinHai agent."""

import time
import random
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
from linhai.llm import ChatMessage

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


class MessageWidget(Static):
    """单条消息显示组件"""

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

    def append_content_lazy(self, new_content: str) -> bool:
        """追加内容到消息"""
        self.content_str += new_content
        if time.perf_counter() - self.last_update_time > 0.1:
            self.last_update_time = time.perf_counter()
            self.update_display()
            return True
        return False

    def update_display(self) -> None:
        """更新消息显示"""
        self.remove_children()
        content_to_display = self.content_str
        if self.is_reasoning:
            # 只显示思考内容的最后5行
            lines = content_to_display.splitlines()
            if len(lines) > 5:
                content_to_display = "\n".join(lines[-5:])
        border_color = {
            "user": "yellow",
            "assistant": "green",
            "assistant-reasoning": "grey50",
        }.get(self.role, "grey50")
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
        self.mount(Static(panel))

    def to_message(self) -> ChatMessage:
        """转换为ChatMessage"""
        return ChatMessage(role=self.role, message=self.content_str)

