from asyncio import Queue
from typing import List
import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Input
from textual import events
from rich.syntax import Syntax
from rich.panel import Panel
from linhai.llm import Message, ChatMessage, AnswerToken, Answer
from linhai.agent import Agent


class MessageWidget(Static):
    """单条消息显示组件"""

    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.content = content

    def append_content(self, new_content: str) -> None:
        """追加内容到消息"""
        self.content += new_content
        self.update_display()

    def update_display(self) -> None:
        """更新消息显示"""
        self.remove_children()
        panel = Panel(
            Syntax(
                self.content, "markdown", theme="nord-darker", background_color="#2E3440"
            ),
            border_style="yellow" if self.role == "user" else "green",
            title="user" if self.role == "user" else "agent",
            title_align="left",
            expand=True,
            style="on #2E3440",
        )
        self.mount(Static(panel))

    def to_message(self) -> ChatMessage:
        """转换为ChatMessage"""
        return ChatMessage(role=self.role, message=self.content)


class CLIApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #2E3440;
    }
    #chat-container {
        height: 80%;
        overflow-y: auto;
        background: #2E3440;
    }
    #input {
        height: 20%;
        background: #2E3440;
        border: round yellow;
    }
    MessageWidget Panel {
        width: 100%;
    }
    """

    def __init__(
        self,
        agent: Agent,
        user_input_queue: "Queue[ChatMessage]",
        user_output_queue: "Queue[Answer | AnswerToken]",
    ):
        super().__init__()
        self.messages: List[Message] = []
        self.agent = agent
        self.user_input_queue = user_input_queue
        self.user_output_queue = user_output_queue
        self.current_response_buffer = ""
        self.output_watcher_task = None
        self.agent_task = None

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

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入"""
        if event.value:
            # 添加用户消息
            user_msg = ChatMessage(role="user", message=event.value)
            self.messages.append(user_msg)
            await self.user_input_queue.put(user_msg)
            event.input.value = ""
            # 更新UI
            widget = MessageWidget(user_msg.role, user_msg.message)
            self.query_one("#chat-container").mount(widget)
            self.query_one("#chat-container").scroll_end()
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
                if current_message is None:
                    # 创建新消息
                    current_message = MessageWidget(
                        role="assistant", content=output["content"]
                    )
                    await asyncio.sleep(0)
                    self.query_one("#chat-container").mount(current_message)
                    self.messages.append(current_message.to_message())
                else:
                    current_message.append_content(output["content"])
                current_message.update_display()
                self.query_one("#chat-container").scroll_end()
            else:  # Answer
                tool_call = output.get_tool_call()
                if tool_call:
                    # 处理工具调用
                    tool_message = f"{tool_call.function_name}(...)"
                    msg = ChatMessage(role="assistant", message=tool_message)
                    await self.add_bot_message(msg)
                current_message = None

    async def on_mount(self) -> None:
        """应用挂载时启动输出队列监听"""
        self.output_watcher_task = asyncio.create_task(self.watch_output_queue())
        self.agent_task = asyncio.create_task(self.agent.run())

    async def on_unmount(self) -> None:
        """应用卸载时取消任务"""
        if self.output_watcher_task:
            self.output_watcher_task.cancel()
        if self.agent_task:
            self.agent_task.cancel()

    async def on_key(self, event: events.Key) -> None:
        """处理键盘事件"""
        if event.key == "ctrl+c":
            self.app.exit()
