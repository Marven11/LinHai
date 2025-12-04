"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from typing import (
    cast,
    Sequence,
)

import asyncio

from .base import (
    RuntimeMessage,
    AgentContext,
)
from .lifecycle import Lifecycle
from .message import AgentMessage
from .orchestration import AgentMessageOrchestration
from .toolcall import AgentToolcall
from linhai.markdown_parser import extract_tool_calls_with_errors, ParseError
from linhai.llm import (
    Message,
    LanguageModel,
    Answer,
    OpenAiAnswer,
    ToolCallMessage,
)
from linhai.group_chat import GroupChat
from linhai.type_hints import AgentState
from linhai.tool.mcp_connector import MCPConnector
from linhai.utils import CliRuntimeNotice
from .workflow import compress_history_range
from linhai.input_parser import parse_user_input


class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

    def __init__(
        self,
        context: AgentContext,
        group_chat: GroupChat,
        init_messages: Sequence[Message],
    ):
        self.context = context
        self.group_chat = group_chat

        group_chat.register_queue("user_message")
        group_chat.register_member("agent", self)

        self.mcp_connector: MCPConnector | None = None

        self.state: AgentState = "waiting_user"

        self.lifecycle = Lifecycle(group_chat)
        self.message_processor = AgentMessage(group_chat, init_messages)
        self.orchestration = AgentMessageOrchestration(group_chat, self.message_processor)
        self.toolcall_processor = AgentToolcall(self)

        self.last_token_usage = None
        self.current_enable_compress = True
        self.soft_compress_triggered = False

        self.compress_tool_called_in_last_response = False
        self.current_disable_waiting_user_warning = False

        self.last_threshold_state = None

        self.current_answer: Answer | None = None

        self.messages = self.message_processor.get_messages()

        self.queued_messages: list = []

    def get_threshold_info(self) -> tuple[int, int, int, int, float] | None:
        if not self.last_token_usage:
            return None

        current_llm = self.context["llms"][self.context["current_llm_index"]]
        token_limit = current_llm.get_token_limit()

        if token_limit is None:
            token_limit = 65536

        soft_config = self.context.get("compress_threshold_soft", 0.5)
        hard_config = self.context.get("compress_threshold_hard", 0.8)

        compress_threshold_soft = (
            int(soft_config * token_limit)
            if isinstance(soft_config, float)
            else soft_config
        )
        compress_threshold_hard = (
            int(hard_config * token_limit)
            if isinstance(hard_config, float)
            else hard_config
        )

        taken = (
            0.0
            if self.last_token_usage <= compress_threshold_soft
            else (
                (self.last_token_usage - compress_threshold_soft)
                / (compress_threshold_hard - compress_threshold_soft)
            )
        )
        remaining = compress_threshold_hard - self.last_token_usage
        return (
            compress_threshold_soft,
            compress_threshold_hard,
            self.last_token_usage,
            remaining,
            taken,
        )

    async def interrupt(self, custom_message: str | None = None):
        """
        打断当前Answer并添加自定义消息。

        参数:
            custom_message: 自定义消息内容，如果为None则使用默认消息
        """
        if self.current_answer:
            self.current_answer.interrupt()
            await self.group_chat.send("agent_answer", self.current_answer)

            if custom_message:
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content=custom_message
                )
                self.message_processor.append_message(RuntimeMessage(custom_message))
            else:
                interrupt_msg = CliRuntimeNotice(level="WARNING", content="Agent被打断")
                self.message_processor.append_message(RuntimeMessage("Agent被打断"))

            if "```json toolcall" in self.current_answer.get_current_content():
                self.message_processor.append_message(
                    RuntimeMessage("当前所有工具调用全部被忽略，请重新调用")
                )

            self.current_answer = None

            await self.group_chat.send_if_exists("ui_log", interrupt_msg)
            self.state = "working"

    async def receive_one_user_message(self):
        msg = await self.group_chat.receive("user_message")
        from linhai.llm import UserMessage

        assert isinstance(msg, UserMessage)
        await self.handle_user_message(msg)
        self.state = "working"
        return msg

    async def state_waiting_user(self):
        """
        处理等待用户状态。

        在这个状态下，Agent会等待用户输入消息，然后处理这些消息。
        """
        if self.is_last_message_user():
            self.state = "working"
            return

        await self.lifecycle.trigger_before_waiting_user(self)

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(level="INFO", content="Agent正在等待用户"),
        )
        while self.group_chat.is_empty("user_message") and self.state == "waiting_user":
            await asyncio.sleep(0.01)
        if self.state != "waiting_user":
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(level="INFO", content="Agent在等待用户时被切换状态"),
            )
            return
        await self.receive_one_user_message()

        await self.generate_response()

    async def state_working(self):
        """
        处理自动运行状态。

        在这个状态下，Agent会自动处理消息并生成响应，
        同时监控token使用量并在需要时触发压缩。
        """

        if not self.group_chat.is_empty("user_message"):
            try:
                await self.receive_one_user_message()
                await self.generate_response()
            except RuntimeError as e:
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

        await self.orchestration.check_and_handle_threshold(self)

    def is_last_message_user(self) -> bool:
        if not self.message_processor.get_messages():
            return False
        msg = self.message_processor.get_messages()[-1]
        from linhai.llm import UserMessage

        return isinstance(msg, UserMessage)

    async def handle_user_message(self, msg: "Message"):
        """处理并加入用户的消息"""
        from linhai.llm import UserMessage

        assert isinstance(msg, UserMessage)

        content = msg.message.strip()

        parsed_input = parse_user_input(content)

        if parsed_input.switch_model:
            llm_name = parsed_input.switch_model
            if llm_name in self.context["llm_names"]:
                self.context["current_llm_index"] = self.context["llm_names"].index(
                    llm_name
                )
                self.message_processor.append_message(
                    RuntimeMessage(f"用户把你的底层LLM切换为了{llm_name!r}")
                )
            else:

                self.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：用户指定的LLM名称{llm_name!r}不存在，请向用户报告这一点"
                    )
                )

        if parsed_input.command == "queue":
            self.queued_messages.append(msg)
        elif parsed_input.command in ["quit", "exit"]:
            await self.group_chat.send("exit_signal", {"return_code": 0})
        else:
            self.message_processor.append_message(msg)

    async def get_current_model(self) -> LanguageModel:
        """
        根据当前LLM索引选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        return self.context["llms"][self.context["current_llm_index"]]

    async def generate_response(
        self, enable_compress: bool = True, disable_waiting_user_warning: bool = False
    ) -> Answer:
        """
        生成回复并发送给用户。

        参数:
            enable_compress: 是否启用压缩功能
            disable_waiting_user_warning: 是否禁用等待用户警告

        返回:
            Answer: 生成的回答对象
        """
        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            from linhai.llm import AssistantMessage

            if isinstance(last_msg, AssistantMessage):
                llm_msg = last_msg.to_llm_message()
                if llm_msg.get("role") == "assistant":
                    empty_user_msg = RuntimeMessage("继续")
                    self.message_processor.append_message(empty_user_msg)

        self.current_enable_compress = enable_compress
        self.current_disable_waiting_user_warning = disable_waiting_user_warning

        await self.lifecycle.trigger_before_message_generation(
            enable_compress, disable_waiting_user_warning
        )

        model = await self.get_current_model()

        answer: Answer = await model.answer_stream(
            self.message_processor.get_messages()
        )

        self.current_answer = answer

        async for token in answer:
            await self.group_chat.send("agent_answer", token)

            current_content = answer.get_current_content()

            interrupted = await self.lifecycle.trigger_during_message_generation(
                answer, current_content
            )
            if interrupted:
                return answer

            if not self.group_chat.is_empty("user_message"):
                msg = await self.receive_one_user_message()
                from linhai.llm import UserMessage

                assert isinstance(msg, UserMessage)
                parsed_input = parse_user_input(msg.message.strip())
                if parsed_input.command is None:
                    await self.group_chat.send("agent_answer", answer)
                    chat_message = answer.get_message()
                    self.message_processor.append_message(chat_message)
                    await self.interrupt("Agent被用户打断")
                    await self.handle_user_message(msg)
                    return answer

        await self.group_chat.send("agent_answer", answer)

        from linhai.llm import AssistantMessage

        chat_message = cast(AssistantMessage, answer.get_message())
        full_response = chat_message.message
        self.message_processor.append_message(chat_message)

        if self.queued_messages:
            await self.group_chat.send_if_exists(
                "ui_log", CliRuntimeNotice(level="INFO", content="排队消息被处理")
            )
            self.message_processor.append_message(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            for msg in self.queued_messages:
                self.message_processor.append_message(msg)
            self.queued_messages = []

        try:
            tool_calls, errors = extract_tool_calls_with_errors(full_response)
        except ParseError:
            interrupt_msg = CliRuntimeNotice(
                level="WARNING", content="工具调用格式出错"
            )
            await self.group_chat.send_if_exists("ui_log", interrupt_msg)

            self.message_processor.append_message(RuntimeMessage("工具调用格式出错"))
            return answer

        for error in errors:
            self.message_processor.append_message(RuntimeMessage(error))

        self.toolcall_processor.start_new_tool_call_round()

        for call in tool_calls:
            if "name" in call and "arguments" in call:
                tool_call = ToolCallMessage(
                    function_name=call["name"],
                    function_arguments=call["arguments"],
                )
                await self.toolcall_processor.call_tool(tool_call)

        if self.toolcall_processor.early_return:
            return await self.generate_response()

        if isinstance(answer, OpenAiAnswer):
            self.last_token_usage = answer.total_tokens

        await self.lifecycle.trigger_after_message_generation(
            answer, full_response, tool_calls
        )

        await self.save_conversation_history()

        self.current_answer = None
        return answer

    def get_current_llm_info(self) -> tuple[str, LanguageModel]:
        """获取当前LLM的名称和实例。

        返回:
            tuple[str, LanguageModel]: (LLM名称, LLM实例)
        """
        current_index = self.context["current_llm_index"]
        llm_name = self.context["llm_names"][current_index]
        llm_instance = self.context["llms"][current_index]
        return llm_name, llm_instance

    async def save_conversation_history(self):
        """保存对话历史到文件。"""
        await self.message_processor.save_conversation_history()

    async def run(self):
        """
        Agent主循环，负责状态机的管理和状态切换。

        根据当前状态调用相应的状态处理函数，
        并处理异常和取消事件。
        """

        user_input_found = False
        await self.toolcall_processor.postinit()
        while not self.group_chat.is_empty("user_message"):
            await self.receive_one_user_message()
            user_input_found = True
        if user_input_found:
            await self.generate_response()

        while True:
            try:
                if self.state == "waiting_user":
                    await self.state_waiting_user()
                elif self.state == "working":
                    await self.state_working()
                else:

                    break

            except asyncio.CancelledError:
                break
            await asyncio.sleep(0)

        await self.group_chat.get_members(
            "mcp_connector", MCPConnector
        ).disconnect_all_mcp_servers()
