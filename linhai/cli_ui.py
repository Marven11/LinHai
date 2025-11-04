"""Command-line interface for LinHai agent."""

from typing import List, Optional, cast
import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Input
from textual import events
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from linhai.llm import (
    Message,
    ChatMessage,
    AnswerToken,
    AnswerTokenUsage,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.agent import Agent
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice

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
        self.rainbow_colors: list[Style] = self._generate_rainbow_colors()

    def _generate_rainbow_colors(self) -> list[Style]:
        """使用HSL颜色空间生成平滑的彩虹颜色样式列表"""
        import colorsys
        num_colors = 144
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
        return styles

    def on_mount(self) -> None:
        """组件挂载时启动动画"""
        self.set_interval(0.05, self._update_animation)

    def _update_animation(self) -> None:
        """更新动画时间索引并重新渲染"""
        self.time_index += 1
        self.update(self._render_ascii_art())

    def _render_ascii_art(self) -> Text:
        """渲染带斜向彩虹渐变色的ASCII艺术"""
        text = Text()
        lines = self.ascii_art.splitlines()
        for row, line in enumerate(lines):
            for col, char in enumerate(line):
                # 计算颜色索引：斜向渐变，使用 (row + col + time_index) % len(rainbow_colors)
                color_index = (row + col + self.time_index) // 2 % len(self.rainbow_colors)
                style = self.rainbow_colors[color_index]
                text.append(char, style=style)
            if row < len(lines) - 1:
                text.append("\n")
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
        level_style = {
            "INFO": "grey50",
            "WARNING": "yellow",
            "ERROR": "red"
        }.get(self.level, "grey50")
        
        # 创建消息文本
        message_text = Text()
        message_text.append(f"[{self.level[0]}]", style=level_style)
        message_text.append(f" {self.content}")
        
        yield Static(message_text)


class MessageWidget(Static):
    """单条消息显示组件"""

    def __init__(self, role: str, content: str, is_reasoning: bool = False):
        super().__init__()
        self.role = role
        self.content_str = content
        self.is_reasoning = is_reasoning
        if is_reasoning:
            self.role += "-reasoning"

    def append_content_lazy(self, new_content: str) -> None:
        """追加内容到消息"""
        self.content_str += new_content
        self.update_display()

    def update_display(self) -> None:
        """更新消息显示"""
        self.remove_children()
        content_to_display = self.content_str
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
            border_style={
                "user": "yellow",
                "assistant": "green",
                "assistant-reasoning": "grey50",
            }.get(self.role, "grey50"),
            title=self.role,
            title_align="left",
            expand=True,
            style="on #2E3440",
        )
        self.mount(Static(panel))

    def to_message(self) -> ChatMessage:
        """转换为ChatMessage"""
        return ChatMessage(role=self.role, message=self.content_str)


class CLIApp(App):
    """Textual-based CLI application for LinHai agent interaction."""

    CSS = """
    Screen {
        layout: vertical;
        background: #2E3440;
    }
    #chat-container {
        min-height: 60%;
        background: #2E3440;
    }
    #input {
        height: 3;
        background: #2E3440;
        border: round yellow;
    }
    #token-usage {
        width: 100%;
        height: 1;
        background: #101520;
        color: #474e5b;
    }
    .welcome-message {
        width: 100%;
        text-align: center;
        content-align: center middle;
    }
    """

    MAX_MESSAGES = 1000

    def __init__(
        self,
        group_chat: GroupChat,
        init_messages: list[str] | None = None,
    ):
        super().__init__()
        self.messages: List[Message] = []
        self.group_chat = group_chat
        self.group_chat.register_queue("cli_agent_output")
        self.group_chat.register_queue("cli_runtime_output")
        self.group_chat.register_queue("cli_exit")
        group_chat.register_member("cli_app", self)

        self.init_messages = init_messages

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.current_tool_call: Optional[ToolCallMessage] = None
        self.current_tool_confirmation: Optional[ToolConfirmationMessage] = None
        self.current_token_usage: AnswerTokenUsage | None = None
        self.cumulative_token_usage: dict[str, int] | None = None
        self.last_user_scroll_time: float | None = None  # 记录用户上次滚动时间

    def compose(self) -> ComposeResult:
        """组合UI组件"""
        with VerticalScroll(id="chat-container"):
            for msg in self.messages:
                llm_message = msg.to_llm_message()
                content = None
                if "content" in llm_message:
                    content = str(llm_message["content"])
                elif "function_call" in llm_message:
                    content = f"{llm_message['function_call']}(...)"
                else:
                    content = f"<Unknown {llm_message!r}>"
                yield MessageWidget(role=llm_message["role"], content=content)

        yield Input(placeholder="输入消息...", id="input")
        yield Static("", id="token-usage")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入"""
        if self.current_tool_call:
            # 处理工具确认响应
            user_input = event.value.strip().lower()
            if user_input in ["y", "yes", "是"]:
                confirmed = True
            elif user_input in ["n", "no", "否"]:
                confirmed = False
            else:
                # 无效输入，提示重新输入
                event.input.value = ""
                cast(Input, self.query_one("#input")).placeholder = (  # type: ignore
                    "请输入 'y' 或 'n' 来确认工具调用"
                )
                return

            # 发送确认消息
            self.current_tool_confirmation = ToolConfirmationMessage(
                tool_call=self.current_tool_call, confirmed=confirmed
            )

            # 重置当前工具请求
            self.current_tool_call = None
            event.input.value = ""
            cast(Input, self.query_one("#input")).placeholder = "输入消息..."  # type: ignore
            return

        if event.value:
            # 隐藏欢迎消息
            container = self.query_one("#chat-container")
            welcome_widgets = container.query(".welcome-message")
            for widget in welcome_widgets:
                widget.remove()
            
            # 添加用户消息
            user_msg = ChatMessage(role="user", message=event.value)
            self.messages.append(user_msg)
            await self.group_chat.send("agent_user_input", user_msg)
            event.input.value = ""
            # 更新UI
            widget = MessageWidget(user_msg.role, user_msg.message)
            container.scroll_end()
            container.mount(widget)
            widget.update_display()

    async def add_bot_message(self, message: Message) -> None:
        """添加机器人消息"""
        llm_message = message.to_llm_message()
        self.messages.append(message)
        content = None
        if "content" in llm_message:
            content = str(llm_message["content"])
        elif "function_call" in llm_message:
            content = f"{llm_message['function_call']}(...)"
        else:
            content = f"<Unknown {llm_message!r}>"
        widget = MessageWidget("agent", content)
        self.query_one("#chat-container").mount(widget)
        self.query_one("#chat-container").scroll_end()
        self._trim_messages_if_needed()

    async def watch_output_queue(self):
        """监听输出队列并更新UI"""
        current_message = None
        while True:
            # 同时监听三个队列
            agent_output_task = asyncio.create_task(self.group_chat.receive("cli_agent_output"))
            runtime_output_task = asyncio.create_task(self.group_chat.receive("cli_runtime_output"))
            exit_task = asyncio.create_task(self.group_chat.receive("cli_exit"))
            
            done, pending = await asyncio.wait(
                [agent_output_task, runtime_output_task, exit_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消未完成的任务
            for task in pending:
                task.cancel()
            
            # 处理完成的任务
            for task in done:
                output = task.result()
                
                # 检查是否是退出任务
                if task == exit_task:
                    if isinstance(output, dict) and "return_code" in output:
                        return_code = output["return_code"]
                        self.exit(return_code=return_code)
                        return  # 立即返回，不再处理其他消息
                    continue  # 跳过其他处理
                
                if isinstance(output, CliRuntimeNotice):
                    # 处理运行时消息
                    container = self.query_one("#chat-container")
                    widget = RuntimeMessageWidget(level=output.level, content=output.content)
                    container.mount(widget)
                    container.scroll_end()
                    self._trim_messages_if_needed()
                elif isinstance(output, AnswerToken):
                    if output.reasoning_content:
                        is_reasoning = True
                        content = output.reasoning_content
                    else:
                        is_reasoning = False
                        content = output.content
                    if not content:
                        continue

                    if current_message and current_message.is_reasoning != is_reasoning:
                        current_message = None

                    container = self.query_one("#chat-container")
                    should_scroll = (
                        container.is_vertical_scroll_end or
                        container.scroll_offset.y >= container.max_scroll_y - 5
                    ) and not self.is_user_recently_scrolled()

                    if current_message is None:

                        current_message = MessageWidget(
                            role="assistant", content=content, is_reasoning=is_reasoning
                        )
                        await asyncio.sleep(0)
                        container.mount(current_message)
                        self.messages.append(current_message.to_message())
                        current_message.update_display()
                        self._trim_messages_if_needed()
                    else:
                        current_message.append_content_lazy(content)

                    if should_scroll:
                        container.scroll_end()
                elif isinstance(output, AnswerTokenUsage):
                    self.current_token_usage = output
                elif isinstance(output, dict) and "return_code" in output:
                    # 处理退出信号
                    return_code = output["return_code"]
                    self.exit(return_code=return_code)
                    return  # 立即返回，不再处理其他消息
                elif isinstance(output, Answer):
                    if current_message:
                        current_message.update_display()
                    tool_call = output.get_tool_call()
                    if tool_call:
                        # 处理工具调用
                        tool_message = f"{tool_call.function_name}(...)"
                        msg = ChatMessage(role="assistant", message=tool_message)
                        await self.add_bot_message(msg)

                    # 获取并累加token使用量
                    token_usage = output.get_token_usage()
                    if token_usage is not None:
                        if self.cumulative_token_usage is None:
                            self.cumulative_token_usage = token_usage.model_dump()
                        else:
                            self.cumulative_token_usage[
                                "input_tokens"
                            ] += token_usage.input_tokens
                            self.cumulative_token_usage[
                                "output_tokens"
                            ] += token_usage.output_tokens
                            self.cumulative_token_usage[
                                "total_tokens"
                            ] += token_usage.total_tokens
                        self.current_token_usage = None
                        # 传入当前回答的token长度
                        self.update_token_display(token_usage.total_tokens)

                    current_message = None
                else:
                    raise RuntimeError(f"Unknown Type: {type(output)=} {output=}")

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())

        # 如果有初始消息，自动发送
        if self.init_messages:
            for init_message in self.init_messages:
                user_msg = ChatMessage(role="user", message=init_message)
                self.messages.append(user_msg)
                await self.group_chat.send("agent_user_input", user_msg)
                # 更新UI
                widget = MessageWidget(user_msg.role, user_msg.message)
                container = self.query_one("#chat-container")
                container.scroll_end()
                container.mount(widget)
                widget.update_display()
        else:
            # 显示欢迎消息（如果没有初始消息）
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, _llm = agent.get_current_llm_info()
            version = "v0.1.0"
            
            # 创建彩虹ASCII艺术组件
            rainbow_art = RainbowAsciiArt(ASCII_ART)
            rainbow_art.add_class("welcome-message")
            container = self.query_one("#chat-container")
            container.mount(rainbow_art)
            
            # 显示版本信息
            version_text = f"版本: {version}\nLLM: {llm_name}"
            version_widget = Static(version_text)
            version_widget.add_class("welcome-message")
            container.mount(version_widget)
            container.scroll_end()

        self.agent_task = asyncio.create_task(
            self.group_chat.get_members("agent", Agent).run()
        )


        cliapp_tool = ToolSet()

        @cliapp_tool.register_tool(
            name="exit_app",
            desc="退出agent并关闭APP",
            args={
                "return_code": ToolArgInfo(
                    desc="退出代码，0表示成功，非0表示错误", type="int"
                ),
            },
            required_args=["return_code"],
        )
        def _exit_app(return_code: int):
            """退出Agent程序，指定返回代码

            Args:
                return_code: 退出代码，0表示成功，非0表示错误

            Returns:
                退出消息（实际上程序会退出，所以不会返回）
            """
            self.exit(return_code=return_code)

        from linhai.tool.main import ToolManager

        self.group_chat.get_members("tool_manager", ToolManager).add_toolset(
            cliapp_tool
        )

    async def on_unmount(self) -> None:
        """应用卸载时取消任务并关闭所有终端"""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.agent_task:
            self.agent_task.cancel()
        
        # 关闭所有终端
        from linhai.tool.tools.terminal import close_all_terminals
        close_all_terminals()

    def update_token_display(self, current_answer_token: int) -> None:
        """更新token使用量显示，包括百分比"""
        if self.cumulative_token_usage is None:
            display_text = "Token usage: Not available"
        else:
            input_tokens = self.cumulative_token_usage["input_tokens"]
            output_tokens = self.cumulative_token_usage["output_tokens"]
            total_tokens = self.cumulative_token_usage["total_tokens"]
            if self.current_token_usage is not None:
                input_tokens += self.current_token_usage.input_tokens
                output_tokens += self.current_token_usage.output_tokens
                total_tokens += self.current_token_usage.total_tokens
   
            # 获取当前LLM的token限制
            agent = self.group_chat.get_members("agent", Agent)
            _, llm_instance = agent.get_current_llm_info()  # Unused variable llm_name
            token_limit = llm_instance.get_token_limit()
            display_text = f"Token: {input_tokens:,} in | {output_tokens:,} out | {total_tokens:,} total"
            if token_limit and token_limit > 0:
                percentage = (current_answer_token / token_limit) * 100
                # 使用进度条样式显示百分比
                filled_bars = int(percentage / 10)  # 每10%一个实心方块
                empty_bars = 10 - filled_bars
                progress_bar = "█" * filled_bars + "▒" * empty_bars
                display_text += f" | {progress_bar} {percentage:.0f}% of {token_limit:,}"
        
        token_display = self.query_one("#token-usage")
        assert isinstance(token_display, Static)
        token_display.update(display_text)



    def _trim_messages_if_needed(self) -> None:
        """如果消息数量超过阈值，修剪旧消息"""

        message_widgets = self.query_one("#chat-container").query(MessageWidget)
        if len(message_widgets) < self.MAX_MESSAGES:
            return
        for i in range(self.MAX_MESSAGES - len(message_widgets)):
            message_widgets[i].remove()

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""
        if event.key == "ctrl+c":
            # 先关闭所有终端，然后退出应用
            from linhai.tool.tools.terminal import close_all_terminals
            close_all_terminals()
            self.app.exit()

    async def on_scroll(self, event: events.Scroll) -> None:
        """监听滚动事件，记录用户滚动时间"""
        import time
        self.last_user_scroll_time = time.time()
        
    def is_user_recently_scrolled(self) -> bool:
        """检查用户是否在最近3秒内滚动了"""
        if self.last_user_scroll_time is None:
            return False
        import time
        current_time = time.time()
        return (current_time - self.last_user_scroll_time) < 3.0

    async def confirm_tool_request(self, tool_call: ToolCallMessage):
        """向用户确认是否需要调用工具"""
        self.current_tool_confirmation = None
        self.current_tool_call = tool_call
        # 显示确认提示
        self.query_one("#input").placeholder = (  # type: ignore
            f"确认执行工具 {tool_call.function_name} 吗？(y/n)"
        )
        # 等待用户输入（通过 on_input_submitted 处理）
        while self.current_tool_confirmation is None:
            await asyncio.sleep(0.01)
        return self.current_tool_confirmation
