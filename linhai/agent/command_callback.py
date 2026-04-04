from typing import Literal

from linhai.llm import UserMessage, ToolCallMessage
from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.agent.user_message_handler import ParsedUserMessage


class CommandCallback:
    def __init__(self, registry: Registry):
        self.registry = registry

    async def __call__(self, parsed: ParsedUserMessage) -> bool | None:
        parsed_input = parsed["parsed_input"]
        msg = parsed["raw_message"]

        if parsed_input.switch_model:
            return await self._handle_switch_model(parsed_input.switch_model, msg)

        if parsed_input.command:
            if parsed_input.command == "context_forget_large_message":
                return await self._handle_context_tool_command(parsed_input)
            if parsed_input.command == "queue":
                return await self._handle_queue_command(msg)
            if parsed_input.command in ("quit", "exit"):
                return await self._handle_quit_command()
            if parsed_input.command == "help":
                return await self._handle_help_command()
            if parsed_input.command == "status":
                return await self._handle_status_command()

        return None

    @staticmethod
    def get_command_completions() -> list[str]:
        return [
            "/queue",
            "/help",
            "/status",
            "/quit",
            "/exit",
            "/context_forget_large_message",
        ]

    async def _show_runtime_message(
        self, level: Literal["INFO", "WARNING", "ERROR"], content: str
    ) -> None:
        await self.registry.send_if_exists(
            "ui_log", UiNotice(level=level, content=content)
        )

    async def _handle_queue_command(self, msg: UserMessage) -> bool:
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        queue_content = msg.message.removeprefix("/queue").strip()
        if not queue_content:
            await self._show_runtime_message("ERROR", "用法: /queue <消息内容>")
            return False

        queued_msg = UserMessage(message=queue_content)
        agent.queued_messages.append(queued_msg)
        return False

    async def _handle_quit_command(self) -> bool:
        await self.registry.send("exit_signal", {"return_code": 0})
        return False

    async def _handle_help_command(self) -> bool:
        help_text = (
            "可用命令:\n"
            "/queue <消息> - 将消息加入排队列表,在下次回答后处理\n"
            "\n"
            "/status - 显示当前状态信息\n"
            "/help - 显示此帮助信息\n"
            "/quit, /exit - 退出程序\n"
            "@<模型名> - 切换底层LLM模型\n"
            "\n"
            "上下文工具:\n"
            "/context_forget_large_message - 清理大消息\n"
        )
        await self._show_runtime_message("INFO", help_text)
        return False

    async def _handle_status_command(self) -> bool:
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm_name, _llm = agent.get_current_llm_info()
        threshold_info = agent.get_threshold_info()

        status_lines = [f"当前LLM: {llm_name}", f"当前状态: {agent.state}"]

        if threshold_info:
            usage_percent = threshold_info["usage_ratio"] * 100
            status_lines.append(
                f"Token使用: {threshold_info['used_tokens']}/{threshold_info['hard_limit']} ({usage_percent:.1f}%)"
            )

        await self._show_runtime_message("INFO", "\n".join(status_lines))
        return False

    async def _handle_switch_model(self, model_name: str, msg: UserMessage) -> bool:
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        llm_manager = agent.llm_manager

        await agent.message_processor.add_new_message(msg)

        if model_name == "default":
            await llm_manager.switch_to_llm(llm_manager.default_llm_name)
            await self._show_runtime_message("INFO", "已将底层LLM切换为默认LLM")
        elif model_name in llm_manager.llm_names:
            await llm_manager.switch_to_llm(model_name)
            await self._show_runtime_message(
                "INFO", f"已将底层LLM切换为 {model_name!r}"
            )
        else:
            await self._show_runtime_message(
                "ERROR",
                f"错误：LLM名称 {model_name!r} 不存在.可用的LLM包括: {', '.join(llm_manager.llm_names)}",
            )

        return True

    async def _handle_context_tool_command(self, parsed_input) -> bool:
        from .main import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)

        await self._show_runtime_message(
            "INFO", f"正在执行命令: {parsed_input.command}"
        )

        tool_call = ToolCallMessage(
            function_name=parsed_input.command,
            function_arguments={},
            assert_success=False,
            with_secret=[],
        )

        await agent.toolcall_processor.call_tool(tool_call, tool_index=1)

        await self._show_runtime_message(
            "INFO",
            f"上下文工具命令执行成功: {parsed_input.command}",
        )

        return True
