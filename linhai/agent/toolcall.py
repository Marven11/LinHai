"""工具调用处理模块，负责工具注册、调用和结果管理。"""

import time
from pathlib import Path
from typing import cast

from linhai.base import (
    OpenAiToolResultMessage,
    ToolCallMessage,
    Message,
)
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.tool.base import (
    ToolArgInfo,
    ToolCallResultMessage,
    SuccessfulToolResult,
    FailedToolResult,
    ToolSet,
    ToolResult,
)
from linhai.tool.main import ToolManager
from linhai.type_hints import NativeToolCallResult
from linhai.utils.tokenizer import count_tokens, get_cl100k_base_tokenizer
from linhai.utils.i18n import t
from linhai.utils.common import UiNotice

from .lifecycle import Lifecycle
from .message import AgentMessage
from .messages import RuntimeMessage
from .state_machine import AgentStateMachine

EARLY_RETURN_SKIP_MESSAGE = "工具调用被跳过（本轮工具调用中有工具执行失败）"


class AgentToolcall:
    """工具调用处理器，负责管理工具注册、调用和结果处理。"""

    def __init__(
        self, registry: Registry, max_toolcall_token_in_round: int | float = 0.3
    ):
        self.registry = registry

        self.early_return = False
        self.current_round_token_count = 0
        self.compress_tool_called_in_last_response = False
        self._pending_warnings: list[RuntimeMessage] = []

        if isinstance(max_toolcall_token_in_round, float):
            llm_manager = registry.get_member_typechecked("llm_manager", LlmManager)
            current_llm = llm_manager.get_current_llm()
            token_limit = current_llm.get_token_limit()
            if token_limit is None:
                token_limit = 65536
            self.max_token_limit = int(max_toolcall_token_in_round * token_limit)
        else:
            self.max_token_limit = max_toolcall_token_in_round

    def calculate_llm_toolset(self) -> ToolSet:
        """计算并返回包含LLM和虚拟工具的toolset."""
        toolset = ToolSet()
        self._register_llm_tools(toolset)
        self._register_dummy_tools(toolset)
        return toolset

    def _register_llm_tools(self, toolset: ToolSet):
        """注册LLM切换工具到给定的toolset."""
        llm_manager = self.registry.get_member_typechecked("llm_manager", LlmManager)
        llm_names = [llm.get_name() for llm in llm_manager.llms]

        desc = t({"zh_CN": "切换到指定的LLM。", "en": "Switch to a specified LLM."})
        if llm_names:
            desc += "可用的LLM包括: " + ", ".join(llm_names)

        @toolset.register_tool(
            name="switch_llm",
            desc=desc,
            args={
                "llm_name": ToolArgInfo(
                    desc=t(
                        {"zh_CN": "要切换到的LLM名称", "en": "LLM name to switch to"}
                    ),
                    schema={"type": "string"},
                ),
            },
            required_args=["llm_name"],
        )
        async def switch_llm(llm_name: str):
            await llm_manager.switch_to_llm(llm_name)
            return SuccessfulToolResult(content=f"已切换到LLM: {llm_name}")

        @toolset.register_tool(
            name="list_llm",
            desc=t(
                {
                    "zh_CN": "列出所有可用的LLM及其状态，包括名称、token限制、是否支持图像等",
                    "en": "List all available LLMs with status including name, model, token limit, image support, etc.",
                }
            ),
            args={},
            required_args=[],
        )
        def list_llm():
            llms_info = llm_manager.list_available_llms()

            assert llms_info, "There is no way agent run without LLM"
            result = []
            result.append(f"找到 {len(llms_info)} 个LLM:")
            for info in llms_info:
                result.append(f"  - 名称: {info['name']}")
                result.append(f"    token限制: {info['token_limit']}")
                result.append(f"    支持图像: {info['support_image']}")
                result.append(f"    当前使用: {info['is_current']}")
                result.append(f"    默认: {info['is_default']}")
                result.append(f"    错误计数: {info['error_count']}")
                result.append("")

            return SuccessfulToolResult(content="\n".join(result))

    def _register_dummy_tools(self, toolset: ToolSet):
        """注册虚拟工具到给定的toolset（token使用情况、历史消息管理等）。"""

        @toolset.register_tool(
            name="get_token_usage",
            desc=t({"zh_CN": "获取token使用情况。", "en": "Get token usage."}),
            args={},
            required_args=[],
        )
        def get_token_usage():
            from ..token_manager import TokenManager

            token_manager = self.registry.get_member_typechecked(
                "token_manager", TokenManager
            )
            if token_manager.cumulative_token_usage is not None:
                total = token_manager.cumulative_token_usage["total_tokens"]
                return SuccessfulToolResult(
                    content=f"当前token总用量为: {total} ({total/1000:.2f} k)"
                )
            else:
                return SuccessfulToolResult(content="暂无token用量信息")

    def _split_and_save_large_output(
        self,
        result_content: str,
        token_count: int,
        tool_name: str,
        single_tool_limit: int,
    ) -> RuntimeMessage:
        """分割并保存过大的工具输出到文件。"""
        conversation_dir = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        long_toolcall_dir = conversation_dir / "long_toolcall"
        long_toolcall_dir.mkdir(exist_ok=True)

        tokenizer = get_cl100k_base_tokenizer()
        tokens = tokenizer.encode(result_content, disallowed_special=())
        parts = []
        total_tokens = len(tokens)
        chunk_size = total_tokens // 3
        for i in range(3):
            start = i * chunk_size
            if i == 2:
                end = total_tokens
            else:
                end = (i + 1) * chunk_size
            part_tokens = tokens[start:end]
            parts.append(tokenizer.decode(part_tokens))

        timestamp = int(time.time())
        filepaths = []
        for idx, part_content in enumerate(parts):
            filename = f"{tool_name}_{timestamp}_part{idx+1}.txt"
            filepath = long_toolcall_dir / filename
            filepath.write_text(part_content, encoding="utf-8")
            filepaths.append(str(filepath))

        if len(parts) > 1:
            return RuntimeMessage(
                f"工具输出过长（{token_count} tokens，超过{single_tool_limit} tokens限制）。已分割保存到 {len(parts)} 个文件: {', '.join(filepaths)}"
            )
        else:
            return RuntimeMessage(
                f"工具输出过长（{token_count} tokens，超过{single_tool_limit} tokens限制）。已保存到文件: {filepaths[0]}"
            )

    def _save_output_to_file(
        self,
        result_content: str,
        token_count: int,
        tool_name: str,
        current_round_token_count: int,
    ) -> RuntimeMessage:
        """保存当前轮次超限的工具输出到文件。"""
        conversation_dir = self.registry.get_member_typechecked(
            "conversation_folder", Path
        )
        long_toolcall_dir = conversation_dir / "long_toolcall"
        long_toolcall_dir.mkdir(exist_ok=True)

        timestamp = int(time.time())
        filename = f"{tool_name}_{timestamp}.txt"
        filepath = long_toolcall_dir / filename
        filepath.write_text(result_content, encoding="utf-8")

        return RuntimeMessage(
            f"当前轮次token总数已达限制（已使用{current_round_token_count} tokens，当前工具{token_count} tokens超过限制）。工具输出已保存到文件: {filepath}"
        )

    async def _process_callback_result(self, callback_result):
        if callback_result is None:
            return
        self._pending_warnings.extend(callback_result.warnings)
        for notice_text in callback_result.user_notices:
            await self.registry.send_if_exists(
                "ui_log", UiNotice(level="INFO", content=notice_text)
            )

    async def flush_warnings(self):
        if not self._pending_warnings:
            return
        message_processor = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        for warning in self._pending_warnings:
            await message_processor.add_new_message(warning)
        self._pending_warnings.clear()

    def start_new_tool_call_round(self):
        """开始新一轮工具调用"""
        self.early_return = False
        self.current_round_token_count = 0
        self._pending_warnings.clear()

    async def call_tool(self, tool_call: ToolCallMessage, tool_index: int):
        """
        调用工具并处理结果。

        参数:
            tool_call: 工具调用消息
            tool_index: 工具调用的索引（当前消息中的第几个）

        返回:
            bool: 是否需要进行早期返回
        """
        state_machine = self.registry.get_member_typechecked(
            "state_machine", AgentStateMachine
        )
        if state_machine.state == "waiting_user":
            state_machine.transition_to_working()
        if self.early_return:
            return

        compress_tools = [
            "context_forget_range_step1",
            "context_forget_range_step2",
            "context_forget_large_message",
            "mark_messages_as_garbage",
        ]
        self.compress_tool_called_in_last_response = (
            tool_call.function_name in compress_tools
        )

        result = await self._call_tool(tool_call, tool_index)
        if result:
            self.early_return = True
        return result

    async def _tool_result_token_management(
        self,
        tool_call: ToolCallMessage,
        tool_index: int,
        tool_result: Message,
    ) -> Message:
        """处理工具结果的token管理

        返回:
            Message: 处理后的消息
        """

        result_content = tool_result.get_content()
        replaced_tool_result = tool_result
        if result_content is not None:
            token_count = count_tokens(result_content)
            single_tool_limit = self.max_token_limit // 3

            if token_count > single_tool_limit:
                replaced_tool_result = self._split_and_save_large_output(
                    result_content,
                    token_count,
                    tool_call.function_name,
                    single_tool_limit,
                )

            if self.current_round_token_count + token_count > self.max_token_limit:
                replaced_tool_result = self._save_output_to_file(
                    result_content,
                    token_count,
                    tool_call.function_name,
                    self.current_round_token_count,
                )
            else:
                self.current_round_token_count += token_count

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        callback_result = await lifecycle.after_toolcall.trigger(
            tool_name=tool_call.function_name,
            tool_index=tool_index,
            status="success",
            message=replaced_tool_result,
            toolcall_arguments=tool_call.function_arguments,
            with_secret=tool_call.with_secret,
            is_tool_failed_duplicated_error=False,
        )
        if callback_result is not None:
            if callback_result.replacement is not None:
                replacement_content = callback_result.replacement.get_content()
                if (
                    isinstance(replaced_tool_result, ToolCallResultMessage)
                    and replacement_content is not None
                ):
                    replaced_tool_result.result = SuccessfulToolResult(
                        content=replacement_content
                    )
                else:
                    replaced_tool_result = callback_result.replacement
        await self._process_callback_result(callback_result)

        return replaced_tool_result

    async def _call_tool(self, tool_call: ToolCallMessage, tool_index: int) -> bool:
        """调用工具。"""

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        arguments = tool_call.function_arguments
        beforecbs_result = await lifecycle.before_tool_call.trigger(
            tool_call.function_name,
            arguments,
            tool_call.with_secret,
        )
        if isinstance(beforecbs_result, FailedToolResult):
            callback_result = await lifecycle.after_toolcall.trigger(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="failed",
                message=RuntimeMessage(beforecbs_result.content),
                toolcall_arguments=arguments,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            await self._process_callback_result(callback_result)
            msg = f"工具调用失败: {beforecbs_result.content}"
            message_processor = self.registry.get_member_typechecked(
                "agent_message", AgentMessage
            )
            await message_processor.add_new_message(RuntimeMessage(msg))
            return True
        elif isinstance(beforecbs_result, dict):
            arguments = beforecbs_result
            tool_call.function_arguments = arguments

        tool_manager = self.registry.get_member_typechecked("tool_manager", ToolManager)
        message_processor = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )

        try:
            tool_result = await tool_manager.process_tool_call(tool_call, tool_index)

            if isinstance(tool_result, ToolCallResultMessage) and isinstance(
                tool_result.result, FailedToolResult
            ):
                lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
                callback_result = await lifecycle.after_toolcall.trigger(
                    tool_name=tool_call.function_name,
                    tool_index=tool_index,
                    status="failed",
                    message=tool_result,
                    toolcall_arguments=tool_call.function_arguments,
                    with_secret=tool_call.with_secret,
                    is_tool_failed_duplicated_error=False,
                )
                await self._process_callback_result(callback_result)

                await message_processor.add_new_message(tool_result)
                return tool_call.assert_success

            processed_result = await self._tool_result_token_management(
                tool_call, tool_index, tool_result
            )

            await self._handle_tool_result(tool_call, processed_result)
            return False
        except (OSError, IOError) as e:

            lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
            msg = RuntimeMessage(f"工具调用失败: {str(e)} {repr(e)}")
            callback_result = await lifecycle.after_toolcall.trigger(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="failed",
                message=msg,
                toolcall_arguments=arguments,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            await self._process_callback_result(callback_result)

            await message_processor.add_new_message(msg)
            return False

    async def _handle_tool_result(
        self, _tool_call: ToolCallMessage, tool_result: Message
    ):
        """处理工具调用结果。"""

        message_processor = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        await message_processor.add_new_message(tool_result)
        state_machine = self.registry.get_member_typechecked(
            "state_machine", AgentStateMachine
        )
        if state_machine.state == "waiting_user":
            state_machine.transition_to_working()

    async def call_openai_tools(
        self, parsed_tool_calls: list[NativeToolCallResult]
    ) -> None:
        """处理解析后的工具调用列表。

        遍历所有已解析的工具调用，检查type字段区分成功/失败，
        调用对应工具并将结果作为OpenAiToolResultMessage添加到消息列表。
        """
        for i, tc in enumerate(parsed_tool_calls, start=1):
            if self.early_return:
                result_msg = OpenAiToolResultMessage(
                    tool_call_id=tc["id"],
                    content=EARLY_RETURN_SKIP_MESSAGE,
                    tool_name=tc["name"],
                )
                message_processor = self.registry.get_member_typechecked(
                    "agent_message", AgentMessage
                )
                await message_processor.add_openai_tool_result(result_msg, tc["id"])
                continue

            if tc["type"] == "error":
                message_processor = self.registry.get_member_typechecked(
                    "agent_message", AgentMessage
                )
                result_msg = OpenAiToolResultMessage(
                    tool_call_id=tc["id"],
                    content=f"工具调用参数JSON解析失败: {tc['error']}",
                    tool_name=tc["name"],
                )
                await message_processor.add_new_message(result_msg)
                self.early_return = True
                continue

            tool_call = ToolCallMessage(
                function_name=tc["name"],
                function_arguments=tc["arguments"],
                assert_success=True,
                with_secret=None,
            )

            should_early_return = await self._call_openai_tool(tool_call, tc["id"], i)
            if should_early_return:
                self.early_return = True

        await self.flush_warnings()

    async def _call_openai_tool(
        self,
        tool_call: ToolCallMessage,
        tool_call_id: str,
        tool_index: int,
    ) -> bool:
        """调用单个OpenAI工具并返回是否需要early_return。

        Args:
            tool_call: 工具调用消息
            tool_call_id: OpenAI工具调用ID
            tool_index: 工具调用索引

        Returns:
            bool: 是否需要early_return
        """
        state_machine = self.registry.get_member_typechecked(
            "state_machine", AgentStateMachine
        )
        if state_machine.state == "waiting_user":
            state_machine.transition_to_working()

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        arguments = tool_call.function_arguments

        beforecbs_result = await lifecycle.before_tool_call.trigger(
            tool_call.function_name,
            arguments,
            tool_call.with_secret,
        )
        if isinstance(beforecbs_result, FailedToolResult):
            result_msg = OpenAiToolResultMessage(
                tool_call_id=tool_call_id,
                content=beforecbs_result.content,
                tool_name=tool_call.function_name,
            )
            message_processor = self.registry.get_member_typechecked(
                "agent_message", AgentMessage
            )
            callback_result = await lifecycle.after_toolcall.trigger(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="failed",
                message=RuntimeMessage(beforecbs_result.content),
                toolcall_arguments=arguments,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            await self._process_callback_result(callback_result)
            await message_processor.add_openai_tool_result(result_msg, tool_call_id)
            return True
        elif isinstance(beforecbs_result, dict):
            arguments = beforecbs_result
            tool_call.function_arguments = arguments

        tool_manager = self.registry.get_member_typechecked("tool_manager", ToolManager)
        message_processor = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )

        tool_result = await tool_manager.process_tool_call(tool_call, tool_index)

        if isinstance(tool_result, ToolCallResultMessage):
            result_content = tool_result.result.to_llm_content()
            if not isinstance(result_content, str):
                result_content = str(result_content)
            is_failed = isinstance(tool_result.result, FailedToolResult)
        else:
            result_content = tool_result.get_content() or ""
            is_failed = False

        if result_content:
            token_count = count_tokens(result_content)
            single_tool_limit = self.max_token_limit // 3
            if token_count > single_tool_limit:
                result_content = f"工具输出过长（{token_count} tokens，超过{single_tool_limit} tokens限制）"
            elif self.current_round_token_count + token_count > self.max_token_limit:
                result_content = f"当前轮次token总数已达限制（已使用{self.current_round_token_count} tokens）"
            else:
                self.current_round_token_count += token_count

        callback_result = await lifecycle.after_toolcall.trigger(
            tool_name=tool_call.function_name,
            tool_index=tool_index,
            status="failed" if is_failed else "success",
            message=RuntimeMessage(result_content),
            toolcall_arguments=tool_call.function_arguments,
            with_secret=tool_call.with_secret,
            is_tool_failed_duplicated_error=False,
        )
        await self._process_callback_result(callback_result)
        if callback_result is not None and callback_result.replacement is not None:
            replaced_content = callback_result.replacement.get_content()
            if replaced_content is not None:
                result_content = replaced_content

        result_msg = OpenAiToolResultMessage(
            tool_call_id=tool_call_id,
            content=result_content,
            tool_name=tool_call.function_name,
        )
        await message_processor.add_openai_tool_result(result_msg, tool_call_id)

        if state_machine.state == "waiting_user":
            state_machine.transition_to_working()

        return is_failed
