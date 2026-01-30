"""工具调用处理模块，负责工具注册、调用和结果管理。"""

import tiktoken
import time
from typing import TYPE_CHECKING, cast, Any
from pathlib import Path
from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    ToolCallResultMessage,
    ToolResultFailed,
)
from linhai.tool.main import ToolManager
from linhai.llm import ToolCallMessage, Message
from linhai.utils import CliRuntimeNotice
from .base import RuntimeMessage

if TYPE_CHECKING:
    from .main import Agent


class AgentToolcall:
    """工具调用处理器，负责管理工具注册、调用和结果处理。"""

    def __init__(self, agent: "Agent", max_toolcall_token_in_round: int = 30000):
        self.agent = agent
        self.group_chat = agent.group_chat

        self.called_tools_in_round: list[str] = []
        self.early_return = False
        self.current_round_token_count = 0
        self.max_token_limit = max_toolcall_token_in_round

        self._register_default_toolsets()

    def _check_tool_conflict(self, tool_name: str) -> str | None:
        """检查工具调用冲突，返回冲突工具的名字，没有冲突返回None

        冲突规则：conflict_with是有向的。
        如果工具A在其conflict_with列表中包含工具B，那么在一个消息内，如果已经调用了工具B，就不能再调用工具A。
        这代表工具A不能在工具B之后调用，但工具B可以在工具A之后调用（除非工具B也标记了与工具A冲突）。
        因此，只需要检查一个方向：当前工具的conflict_with是否包含已调用工具。
        不需要检查已调用工具的conflict_with是否包含当前工具，因为那表示已调用工具不能在当前工具之后调用，
        但当前工具是在已调用工具之后调用，所以是允许的。

        Args:
            tool_name: 要调用的工具名称

        Returns:
            str | None: 冲突工具的名字，没有冲突返回None
        """

        tool_def = None
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        for toolset in tool_manager.toolsets:
            if toolset.has_tool(tool_name):
                tool_def = toolset.get_tools()[tool_name]
                break

        if not tool_def:
            return None

        conflict_with = tool_def["conflict_with"]
        if conflict_with is None:
            conflict_with = []
        for called_tool in self.called_tools_in_round:
            if called_tool in conflict_with:
                return called_tool

        return None

    def _register_default_toolsets(self):
        """注册默认工具集（LLM切换、虚拟工具）。"""
        self._register_llm_toolset()
        self._register_dummy_toolset()

    def _register_llm_toolset(self):
        """注册LLM切换工具集。"""
        llm_toolset = ToolSet()
        llm_names = self.agent.llm_names
        if not isinstance(llm_names, list):
            llm_names = []

        desc = "切换到指定的LLM。"
        if llm_names:
            desc += "可用的LLM包括: " + ", ".join(llm_names)

        @llm_toolset.register_tool(
            name="switch_llm",
            desc=desc,
            args={
                "llm_name": ToolArgInfo(desc="要切换到的LLM名称", type="str"),
            },
            required_args=["llm_name"],
        )
        def switch_llm(llm_name: str):
            if llm_name not in llm_names:
                available_llms = ", ".join(llm_names) if llm_names else "无可用LLM"
                return f"错误：LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"

            index = llm_names.index(llm_name)
            self.agent.current_llm_index = index
            return f"已切换到LLM: {llm_name}"

        @llm_toolset.register_tool(
            name="current_llm",
            desc="显示当前使用的LLM名称",
            args={},
            required_args=[],
        )
        def current_llm():
            current_name = (
                llm_names[self.agent.current_llm_index] if llm_names else "未知"
            )
            return f"当前使用的LLM: {current_name}"

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        tool_manager.add_toolset(llm_toolset)

    def _register_dummy_toolset(self):
        """注册虚拟工具集（token使用情况、历史消息管理等）。"""
        dummy_toolset = ToolSet()

        @dummy_toolset.register_tool(
            name="get_token_usage",
            desc="获取token使用情况。",
            args={},
            required_args=[],
        )
        def get_token_usage() -> str:
            if self.agent.last_token_usage is not None:
                return f"当前token总用量为: {self.agent.last_token_usage} ({self.agent.last_token_usage/1000:.2f} k)"
            else:
                return "暂无token用量信息"

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)

        tool_manager.add_toolset(dummy_toolset)

        orchestration_toolset = self.agent.orchestration.get_orchestration_toolset()
        tool_manager.add_toolset(orchestration_toolset)

    def _split_and_save_large_output(
        self, 
        result_content: str, 
        token_count: int, 
        tool_name: str, 
        single_tool_limit: int
    ) -> str:
        """分割并保存过大的工具输出到文件。"""
        conversation_dir = self.group_chat.get_members("conversation_folder", Path)
        long_toolcall_dir = conversation_dir / "long_toolcall"
        long_toolcall_dir.mkdir(exist_ok=True)

        tokenizer = tiktoken.get_encoding("cl100k_base")
        tokens = tokenizer.encode(result_content)
        parts = []
        for i in range(0, len(tokens), single_tool_limit // 2):
            part_tokens = tokens[i:i + single_tool_limit // 2]
            parts.append(tokenizer.decode(part_tokens))

        timestamp = int(time.time())
        filepaths = []
        for idx, part_content in enumerate(parts):
            filename = f"{tool_name}_{timestamp}_part{idx+1}.txt"
            filepath = long_toolcall_dir / filename
            filepath.write_text(part_content, encoding="utf-8")
            filepaths.append(str(filepath))

        if len(parts) > 1:
            return f"工具输出过长（{token_count} tokens，超过{single_tool_limit} tokens限制）。已分割保存到 {len(parts)} 个文件: {', '.join(filepaths)}"
        else:
            return f"工具输出过长（{token_count} tokens，超过{single_tool_limit} tokens限制）。已保存到文件: {filepaths[0]}"

    def _save_output_to_file(
        self, 
        result_content: str, 
        token_count: int, 
        tool_name: str, 
        current_round_token_count: int
    ) -> str:
        """保存当前轮次超限的工具输出到文件。"""
        conversation_dir = self.group_chat.get_members("conversation_folder", Path)
        long_toolcall_dir = conversation_dir / "long_toolcall"
        long_toolcall_dir.mkdir(exist_ok=True)

        timestamp = int(time.time())
        filename = f"{tool_name}_{timestamp}.txt"
        filepath = long_toolcall_dir / filename
        filepath.write_text(result_content, encoding="utf-8")

        return f"当前轮次token总数已达限制（已使用{current_round_token_count} tokens，当前工具{token_count} tokens超过限制）。工具输出已保存到文件: {filepath}"

    async def ensure_mcp_connector(self):
        """确保MCP连接器已准备就绪。"""
        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        await tool_manager.ensure_mcp_connector()

    def start_new_tool_call_round(self):
        """开始新一轮工具调用，清空已调用工具记录"""
        self.called_tools_in_round = []
        self.early_return = False
        self.current_round_token_count = 0

    async def call_tool(self, tool_call: ToolCallMessage, tool_index: int):
        """
        调用工具并处理结果。

        参数:
            tool_call: 工具调用消息
            tool_index: 工具调用的索引（当前消息中的第几个）

        返回:
            bool: 是否需要进行早期返回
        """
        if self.agent.state == "waiting_user":
            self.agent.state = "working"

        if self.early_return:
            msg = f"工具调用因先前工具失败被跳过: {tool_call.function_name}"
            self.agent.message_processor.add_new_message(RuntimeMessage(msg))
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content=msg,
                ),
            )
            return

        conflict_tool = self._check_tool_conflict(tool_call.function_name)
        if conflict_tool:
            conflict_msg = f"工具调用冲突: {tool_call.function_name} 与 {conflict_tool} 存在冲突，已阻止调用，剩余工具调用已忽略"

            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="ERROR",
                    content=f"工具调用冲突: {tool_call.function_name} 与 {conflict_tool}",
                ),
            )

            await self.agent.lifecycle.trigger_on_tool_result(
                tool_name=tool_call.function_name,
                tool_index=0,
                status="failed",
                result_content=f"工具调用冲突: {tool_call.function_name} 与 {self.called_tools_in_round}",
                toolcall_arguments=tool_call.function_arguments,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=True,
            )

            self.agent.message_processor.add_new_message(RuntimeMessage(conflict_msg))
            self.early_return = True
            return True

        self.called_tools_in_round.append(tool_call.function_name)

        compress_tools = [
            "context_range_compress",
            "mark_messages_as_garbage",
            "context_garbage_clean",
            "context_thanox",
        ]
        self.agent.compress_tool_called_in_last_response = (
            tool_call.function_name in compress_tools
        )

        skip_result = await self.agent.lifecycle.trigger_on_tool_result(
            tool_name=tool_call.function_name,
            tool_index=tool_index,
            status="skipped",
            result_content=None,
            toolcall_arguments=None,
            with_secret=tool_call.with_secret,
            is_tool_failed_duplicated_error=False,
        )
        if skip_result is True:
            self.early_return = True
            return True

        result = await self._call_tool(tool_call, tool_index)
        if result:
            self.early_return = True
        return result

    async def _tool_result_token_management(
        self,
        tool_call: ToolCallMessage,
        tool_index: int,
        tool_result: Message,
    ) -> tuple[Message, bool]:
        """处理工具结果的token管理

        返回:
            tuple[Message, bool]: (处理后的消息, 是否需要跳过后续处理)
        """

        result_content = ""
        if isinstance(tool_result, ToolCallResultMessage):
            llm_msg = tool_result.to_llm_message()
            assert "content" in llm_msg
            result_content = llm_msg["content"]
        elif isinstance(tool_result, RuntimeMessage):
            result_content = tool_result.message
        else:
            result_content = str(tool_result)

        tokenizer = tiktoken.get_encoding("cl100k_base")
        token_count = len(tokenizer.encode(result_content))

        single_tool_limit = self.max_token_limit // 3
        if token_count > single_tool_limit:
            runtime_msg = self._split_and_save_large_output(
                result_content, token_count, tool_call.function_name, single_tool_limit
            )
            runtime_message = RuntimeMessage(runtime_msg)

            replacement_result = await self.agent.lifecycle.trigger_on_tool_result(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="success",
                result_content=str(runtime_message),
                toolcall_arguments=None,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            if isinstance(replacement_result, RuntimeMessage):
                runtime_message = replacement_result

            return runtime_message, True

        if self.current_round_token_count + token_count > self.max_token_limit:
            runtime_msg = self._save_output_to_file(
                result_content, token_count, tool_call.function_name, self.current_round_token_count
            )
            runtime_message = RuntimeMessage(runtime_msg)

            replacement_result = await self.agent.lifecycle.trigger_on_tool_result(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="success",
                result_content=str(runtime_message),
                toolcall_arguments=None,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            if isinstance(replacement_result, RuntimeMessage):
                runtime_message = replacement_result

            return runtime_message, True

        self.current_round_token_count += token_count

        replacement_result = await self.agent.lifecycle.trigger_on_tool_result(
            tool_name=tool_call.function_name,
            tool_index=tool_index,
            status="success",
            result_content=str(tool_result),
            toolcall_arguments=None,
            with_secret=tool_call.with_secret,
            is_tool_failed_duplicated_error=False,
        )
        if isinstance(replacement_result, RuntimeMessage):
            tool_result = replacement_result

        return tool_result, False

    async def _call_tool(self, tool_call: ToolCallMessage, tool_index: int) -> bool:
        """调用工具。"""

        modified_arguments = await self.agent.lifecycle.trigger_before_tool_call(
            tool_name=tool_call.function_name,
            toolcall_arguments=tool_call.function_arguments,
            with_secret=tool_call.with_secret,
        )
        if modified_arguments is not None:
            tool_call.function_arguments = modified_arguments

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        try:
            tool_result = await tool_manager.process_tool_call(tool_call, tool_index)

            if isinstance(tool_result, ToolCallResultMessage) and isinstance(
                tool_result.result, ToolResultFailed
            ):


                llm_msg = tool_result.to_llm_message()
                assert "content" in llm_msg
                formatted_content = llm_msg["content"]
                await self.agent.lifecycle.trigger_on_tool_result(
                    tool_name=tool_call.function_name,
                    tool_index=tool_index,
                    status="failed",
                    result_content=formatted_content,
                    toolcall_arguments=tool_call.function_arguments,
                    with_secret=tool_call.with_secret,
                    is_tool_failed_duplicated_error=False,
                )
                msg = f"工具调用失败: {tool_result.result.content}"

                self.agent.message_processor.add_new_message(RuntimeMessage(msg))
                if tool_call.assert_success:
                    return True
                else:
                    return False

            processed_result, skip_handle = await self._tool_result_token_management(
                tool_call, tool_index, tool_result
            )

            if skip_handle:
                await self._handle_tool_result(tool_call, processed_result)
                return False

            await self._handle_tool_result(tool_call, processed_result)
            return False
        except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:

            await self.agent.lifecycle.trigger_on_tool_result(
                tool_name=tool_call.function_name,
                tool_index=tool_index,
                status="failed",
                result_content=str(e),
                toolcall_arguments=tool_call.function_arguments,
                with_secret=tool_call.with_secret,
                is_tool_failed_duplicated_error=False,
            )
            msg = f"工具调用失败: {str(e)} {repr(e)}"

            self.agent.message_processor.add_new_message(RuntimeMessage(msg))
            return False

    async def _handle_tool_result(
        self, _tool_call: ToolCallMessage, tool_result: Message
    ):
        """处理工具调用结果。"""

        self.agent.message_processor.add_new_message(tool_result)
        if self.agent.state == "waiting_user":
            self.agent.state = "working"
