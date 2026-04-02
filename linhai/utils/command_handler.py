"""Command handler for TUI commands that should not be sent to agent."""

from typing import Literal

from linhai.registry import Registry
from linhai.utils.common import UiNotice
from linhai.utils.input_parser import parse_user_input


class CommandHandler:
    """处理`/`和`@`命令,这些命令不会发送给agent."""

    def __init__(self, registry: Registry):
        self.registry = registry

    async def handle_command(self, message_text: str) -> tuple[bool, bool]:
        """处理命令,返回(handled, should_interrupt).

        handled: 是否是命令
        should_interrupt: 是否需要打断agent
        """
        parsed_input = parse_user_input(message_text)

        if parsed_input.switch_model:
            return await self._handle_switch_model(
                parsed_input.switch_model, message_text
            )

        if parsed_input.command:
            if parsed_input.command == "context_forget_large_message":
                return await self._handle_context_tool_command(message_text)
            elif parsed_input.command == "queue":
                return await self._handle_queue_command(message_text)

            elif parsed_input.command == "quit" or parsed_input.command == "exit":
                return await self._handle_quit_command()
            elif parsed_input.command == "help":
                return await self._handle_help_command()
            elif parsed_input.command == "status":
                return await self._handle_status_command()

        return False, False

    async def _show_error_message(self, content: str) -> None:
        await self._show_runtime_message("ERROR", content)

    async def _show_success_message(self, content: str) -> None:
        await self._show_runtime_message("INFO", content)

    async def _show_runtime_message(
        self, level: Literal["INFO", "WARNING", "ERROR"], content: str
    ) -> None:
        await self.registry.send_if_exists(
            "ui_log", UiNotice(level=level, content=content)
        )

    async def _handle_queue_command(self, message_text: str) -> tuple[bool, bool]:
        """处理/queue命令,将消息加入排队列表."""
        from linhai.agent import Agent
        from linhai.llm import UserMessage

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True, False

        queue_content = message_text.removeprefix("/queue").strip()
        if not queue_content:
            await self._show_error_message("用法: /queue <消息内容>")
            return True, False

        queued_msg = UserMessage(message=queue_content)
        agent.queued_messages.append(queued_msg)

        return True, False

    async def _handle_quit_command(self) -> tuple[bool, bool]:
        """处理/quit和/exit命令,发送退出信号."""
        await self.registry.send("exit_signal", {"return_code": 0})
        return True, False

    async def _handle_help_command(self) -> tuple[bool, bool]:
        """处理/help命令,显示帮助信息."""
        help_text = """可用命令:
/queue <消息> - 将消息加入排队列表,在下次回答后处理

/status - 显示当前状态信息
/help - 显示此帮助信息
/quit, /exit - 退出程序
@<模型名> - 切换底层LLM模型

上下文工具:
/context_forget_large_message - 清理大消息
"""

        await self._show_runtime_message("INFO", help_text)
        return True, False

    async def _handle_status_command(self) -> tuple[bool, bool]:
        """处理/status命令,显示状态信息."""
        from linhai.agent import Agent

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True, False

        llm_name, _llm = agent.get_current_llm_info()
        threshold_info = agent.get_threshold_info()

        status_lines = [f"当前LLM: {llm_name}", f"当前状态: {agent.state}"]

        if threshold_info:
            usage_percent = threshold_info["usage_ratio"] * 100
            status_lines.append(
                f"Token使用: {threshold_info['used_tokens']}/{threshold_info['hard_limit']} ({usage_percent:.1f}%)"
            )

        await self._show_runtime_message("INFO", "\n".join(status_lines))
        return True, False

    async def _handle_switch_model(
        self, model_name: str, message_text: str
    ) -> tuple[bool, bool]:
        """处理@切换模型命令."""
        from linhai.agent import Agent
        from linhai.llm import UserMessage

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True, False

        llm_manager = agent.llm_manager

        user_msg = UserMessage(message=message_text)
        await agent.message_processor.add_new_message(user_msg)

        if model_name == "default":
            await llm_manager.switch_to_llm(llm_manager.default_llm_name)
            await self._show_success_message("已将底层LLM切换为默认LLM")
        elif model_name in llm_manager.llm_names:
            await llm_manager.switch_to_llm(model_name)
            await self._show_success_message(f"已将底层LLM切换为 {model_name!r}")
        else:
            await self._show_error_message(
                f"错误：LLM名称 {model_name!r} 不存在.可用的LLM包括: {', '.join(llm_manager.llm_names)}"
            )

        return True, True

    def get_command_completions(self) -> list[str]:
        """返回所有支持的命令补全列表"""
        return [
            "/queue",
            "/help",
            "/status",
            "/quit",
            "/exit",
            "/context_forget_large_message",
        ]

    async def _handle_context_tool_command(
        self, message_text: str
    ) -> tuple[bool, bool]:
        parsed_input = parse_user_input(message_text)
        if not parsed_input.command:
            await self._show_error_message("错误：无法解析命令")
            return True, True

        supported_commands = ["context_forget_large_message"]
        if parsed_input.command not in supported_commands:
            await self._show_error_message(
                f"错误：不支持的命令 '{parsed_input.command}',支持的命令有: {', '.join(supported_commands)}"
            )
            return True, True

        from linhai.agent import Agent
        from linhai.llm import ToolCallMessage

        agent = self.registry.get_member_typechecked("agent", Agent)
        if agent is None:
            await self._show_error_message("无法获取agent实例")
            return True, True

        await self._show_success_message(f"正在执行命令: {parsed_input.command}")

        tool_call = ToolCallMessage(
            function_name=parsed_input.command,
            function_arguments={},
            assert_success=False,
            with_secret=[],
        )

        early_return = await agent.toolcall_processor.call_tool(tool_call, tool_index=1)

        if not early_return:
            await self._show_success_message(f"命令{parsed_input.command}执行成功")

            await self.registry.send_if_exists(
                "ui_log",
                UiNotice(
                    level="INFO",
                    content=f"上下文工具命令执行成功: {parsed_input.command}",
                ),
            )

        return True, True
