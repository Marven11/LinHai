"""Command-line interface for LinHai agent."""

from asyncio import Queue
from typing import List, Optional, cast
import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Input
from textual import events
from rich.syntax import Syntax
from rich.panel import Panel
from linhai.llm import (
    Message,
    ChatMessage,
    AnswerToken,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.agent import Agent


class MessageWidget(Static):
    """单条消息显示组件"""

    def __init__(self, role: str, content: str, is_reasoning: bool = False):
        super().__init__()
        self.role = role
        self.content = content
        self.is_reasoning = is_reasoning
        if is_reasoning:
            self.role += "-reasoning"

    def append_content_lazy(self, new_content: str) -> None:
        """追加内容到消息"""
        self.content += new_content
        self.update_display()

    def update_display(self) -> None:
        """更新消息显示"""
        self.remove_children()
        content_to_display = self.content
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
        return ChatMessage(role=self.role, message=self.content)


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
        color: #2E3440;
    }
    """

    def __init__(
        self,
        agent: Agent,
        user_input_queue: "Queue[ChatMessage]",
        user_output_queue: "Queue[Answer | AnswerToken]",
        tool_request_queue: "Queue[ToolCallMessage]",
        tool_confirmation_queue: "Queue[ToolConfirmationMessage]",
        init_message: str | None = None,
    ):
        super().__init__()
        self.messages: List[Message] = []
        self.agent = agent
        self.user_input_queue = user_input_queue
        self.user_output_queue = user_output_queue
        self.tool_request_queue = tool_request_queue
        self.tool_confirmation_queue = tool_confirmation_queue
        self.init_message = init_message
        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.tool_request_watcher_task: Optional[asyncio.Task] = None
        self.current_tool_request: Optional[ToolCallMessage] = None
        self.cumulative_token_usage: dict[str, int] | None = None

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
        if self.current_tool_request:
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
            confirmation = ToolConfirmationMessage(
                tool_call=self.current_tool_request, confirmed=confirmed
            )
            await self.tool_confirmation_queue.put(confirmation)

            # 重置当前工具请求
            self.current_tool_request = None
            event.input.value = ""
            cast(Input, self.query_one("#input")).placeholder = "输入消息..."  # type: ignore
            return

        if event.value:
            # 添加用户消息
            user_msg = ChatMessage(role="user", message=event.value)
            self.messages.append(user_msg)
            await self.user_input_queue.put(user_msg)
            event.input.value = ""
            # 更新UI
            widget = MessageWidget(user_msg.role, user_msg.message)
            container = self.query_one("#chat-container")
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

    async def watch_output_queue(self):
        """监听输出队列并更新UI"""
        current_message = None
        while True:
            output = await self.user_output_queue.get()
            if isinstance(output, dict):  # AnswerToken
                if output["reasoning_content"]:
                    is_reasoning = True
                    content = output["reasoning_content"]
                elif output["content"]:
                    is_reasoning = False
                    content = output["content"]
                else:
                    continue
                if current_message and current_message.is_reasoning != is_reasoning:
                    current_message = None

                container = self.query_one("#chat-container")
                should_scroll = container.is_vertical_scroll_end or (
                    container.scroll_offset.y >= container.max_scroll_y - 2
                )

                if current_message is None:

                    current_message = MessageWidget(
                        role="assistant", content=content, is_reasoning=is_reasoning
                    )
                    await asyncio.sleep(0)
                    container.mount(current_message)
                    self.messages.append(current_message.to_message())
                    current_message.update_display()
                else:
                    current_message.append_content_lazy(content)

                if should_scroll:
                    container.scroll_end()
            else:  # Answer
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
                        self.cumulative_token_usage = token_usage.copy()
                    else:
                        for key in ["input_tokens", "output_tokens", "total_tokens"]:
                            self.cumulative_token_usage[key] += token_usage.get(key, 0)
                    self.update_token_display()

                current_message = None

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())
        self.tool_request_watcher_task = asyncio.create_task(
            self.watch_tool_request_queue()
        )
        self.agent_task = asyncio.create_task(self.agent.run())

        # 如果有初始消息，自动发送
        if self.init_message:
            user_msg = ChatMessage(role="user", message=self.init_message)
            self.messages.append(user_msg)
            await self.user_input_queue.put(user_msg)
            # 更新UI
            widget = MessageWidget(user_msg.role, user_msg.message)
            container = self.query_one("#chat-container")
            container.scroll_end()
            container.mount(widget)
            widget.update_display()

    async def on_unmount(self) -> None:
        """应用卸载时取消任务"""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.agent_task:
            self.agent_task.cancel()

    def update_token_display(self) -> None:
        """更新token使用量显示"""
        if self.cumulative_token_usage is None:
            display_text = "Token usage: Not available"
        else:
            display_text = f"Token: {self.cumulative_token_usage['input_tokens']:,} in | {self.cumulative_token_usage['output_tokens']:,} out | {self.cumulative_token_usage['total_tokens']:,} total"
        token_display = self.query_one("#token-usage")
        token_display.update(display_text)

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""
        if event.key == "ctrl+c":
            self.app.exit()

    async def watch_tool_request_queue(self):
        """监听工具请求队列并显示确认提示"""
        while True:
            tool_request = await self.tool_request_queue.get()
            self.current_tool_request = tool_request
            # 显示确认提示
            self.query_one("#input").placeholder = (  # type: ignore
                f"确认执行工具 {tool_request.function_name} 吗？(y/n)"
            )
            # 等待用户输入（通过 on_input_submitted 处理）
