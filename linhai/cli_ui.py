"""Command-line interface for LinHai agent."""

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
    AnswerTokenUsage,
    Answer,
    ToolCallMessage,
    ToolConfirmationMessage,
)
from linhai.agent import Agent
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.group_chat import GroupChat


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
        self.group_chat.register_queue("cli_user_output")
        group_chat.register_member("cli_app", self)

        self.init_messages = init_messages

        self.current_response_buffer = ""
        self.output_watcher_task: Optional[asyncio.Task] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.current_tool_call: Optional[ToolCallMessage] = None
        self.current_tool_confirmation: Optional[ToolConfirmationMessage] = None
        self.current_token_usage: AnswerTokenUsage | None = None
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
            # 添加用户消息
            user_msg = ChatMessage(role="user", message=event.value)
            self.messages.append(user_msg)
            await self.group_chat.send("agent_user_input", user_msg)
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
        self._trim_messages_if_needed()

    async def watch_output_queue(self):
        """监听输出队列并更新UI"""
        current_message = None
        while True:
            output = await self.group_chat.receive("cli_user_output")
            if isinstance(output, AnswerToken):
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
                    self._trim_messages_if_needed()
                else:
                    current_message.append_content_lazy(content)

                if should_scroll:
                    container.scroll_end()
            elif isinstance(output, AnswerTokenUsage):
                self.current_token_usage = output
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

        self.agent_task = asyncio.create_task(
            self.group_chat.get_members("agent", Agent).run()
        )

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
        def _(return_code: int):
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
        """应用卸载时取消任务"""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.agent_task:
            self.agent_task.cancel()

    def update_token_display(self, current_answer_token: int) -> None:
        """更新token使用量显示，包括百分比"""
        if self.cumulative_token_usage is None:
            display_text = "Token usage: Not available"
        else:
            input_tokens = self.cumulative_token_usage["input_tokens"]
            output_tokens = self.cumulative_token_usage["output_tokens"]
            total_tokens = self.cumulative_token_usage["total_tokens"]
            current_token_usage = 0
            if self.current_token_usage is not None:
                input_tokens += self.current_token_usage.input_tokens
                output_tokens += self.current_token_usage.output_tokens
                total_tokens += self.current_token_usage.total_tokens
                current_token_usage = self.current_token_usage.total_tokens
            
            # 获取当前LLM的token限制
            agent = self.group_chat.get_members("agent", Agent)
            llm_name, llm_instance = agent.get_current_llm_info()
            token_limit = llm_instance.get_token_limit()
            display_text = f"Token: {input_tokens:,} in | {output_tokens:,} out | {total_tokens:,} total"
            if token_limit and token_limit > 0:
                percentage = (current_token_usage / token_limit) * 100
                display_text += f" | {percentage:.1f}% of {token_limit:,}"
        
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
            self.app.exit()

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
