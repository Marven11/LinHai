"""工具调用处理模块，负责工具注册、调用和结果管理。"""

import logging
from typing import TYPE_CHECKING

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.tool.main import ToolManager
from linhai.llm import ToolCallMessage
from linhai.utils import generate_id, CliRuntimeNotice
from .base import RuntimeMessage

if TYPE_CHECKING:
    from .main import Agent

logger = logging.getLogger(__name__)


class AgentToolcall:
    """工具调用处理器，负责管理工具注册、调用和结果处理。"""

    def __init__(self, agent: "Agent"):
        self.agent = agent
        self.group_chat = agent.group_chat
        self.context = agent.context

        self.tool_manager: ToolManager = self.group_chat.get_members(
            "tool_manager", ToolManager
        )

        self.called_tools_in_round: list[str] = []
        self.early_return = False

        self._register_default_toolsets()

    def _check_tool_conflict(self, tool_name: str) -> str | None:
        """检查工具调用冲突，返回冲突工具的名字，没有冲突返回None

        Args:
            tool_name: 要调用的工具名称

        Returns:
            str | None: 冲突工具的名字，没有冲突返回None
        """

        tool_def = None
        for toolset in self.tool_manager.toolsets:
            if toolset.has_tool(tool_name):
                tool_def = toolset.get_tools()[tool_name]
                break

        if not tool_def:
            return None

        for called_tool in self.called_tools_in_round:

            if called_tool in tool_def["conflict_with"]:
                return called_tool

            called_tool_def = None
            for toolset in self.tool_manager.toolsets:
                if toolset.has_tool(called_tool):
                    called_tool_def = toolset.get_tools()[called_tool]
                    break

            if called_tool_def and tool_name in called_tool_def["conflict_with"]:
                return called_tool
        return None

    def _register_default_toolsets(self):
        """注册默认工具集（LLM切换、虚拟工具、工作流工具）。"""
        self._register_llm_toolset()
        self._register_dummy_toolset()
        self._register_workflow_toolset()

    def _register_llm_toolset(self):
        """注册LLM切换工具集。"""
        llm_toolset = ToolSet()
        llm_names = self.context.get(
            "llm_names", [f"llm{i}" for i in range(len(self.context["llms"]))]
        )

        @llm_toolset.register_tool(
            name="switch_llm",
            desc="切换到指定的LLM。可用的LLM包括: " + ", ".join(llm_names),
            args={
                "llm_name": ToolArgInfo(desc="要切换到的LLM名称", type="str"),
            },
            required_args=["llm_name"],
        )
        def switch_llm(llm_name: str):
            if llm_name not in llm_names:
                available_llms = ", ".join(llm_names)
                return f"错误：LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"

            index = llm_names.index(llm_name)
            self.context["current_llm_index"] = index
            return f"已切换到LLM: {llm_name}"

        @llm_toolset.register_tool(
            name="current_llm",
            desc="显示当前使用的LLM名称",
            args={},
            required_args=[],
        )
        def current_llm():
            current_name = llm_names[self.context["current_llm_index"]]
            return f"当前使用的LLM: {current_name}"

        self.tool_manager.add_toolset(llm_toolset)

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

        @dummy_toolset.register_tool(
            name="thanox_history",
            desc="随机删除一半消息（不包括前5条系统消息）。调用这个工具来触发随机删除流程。",
            args={},
            required_args=[],
        )
        async def thanox_history() -> str:
            return await self.agent.message_processor.thanox_history()

        @dummy_toolset.register_tool(
            name="mark_messages_as_garbage",
            desc="将多个消息标记为不需要的垃圾消息。在绿灯、绿闪、黄灯时优先使用此工具标记消息。",
            args={
                "ids": ToolArgInfo(desc="要标记为垃圾的消息的ID", type="list[str]"),
            },
            required_args=["ids"],
        )
        async def mark_messages_as_garbage(ids: list[str]) -> str:
            return self.agent.message_processor.mark_messages_as_garbage(ids)

        @dummy_toolset.register_tool(
            name="message_garbage_clean",
            desc="清理垃圾消息。在红灯时：如果有至少10条垃圾消息则引导agent调用此工具，否则引导调用compress_history_range",
            args={},
            required_args=[],
        )
        async def message_garbage_clean() -> str:
            return await self.agent.message_processor.message_garbage_clean()

        self.tool_manager.add_toolset(dummy_toolset)

    def _register_workflow_toolset(self):
        """注册工作流工具集（历史压缩等）。"""
        workflow_toolset = ToolSet()

        @workflow_toolset.register_tool(
            name="compress_history_range",
            desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            args={},
            required_args=[],
        )
        async def compress_history_range_tool() -> str:
            from .workflow import compress_history_range

            return await compress_history_range(self.agent)

        self.tool_manager.add_toolset(workflow_toolset)

    async def postinit(self):
        await self.tool_manager.ensure_mcp_connector()

    def start_new_tool_call_round(self):
        """开始新一轮工具调用，清空已调用工具记录"""
        self.called_tools_in_round = []
        self.early_return = False

    async def call_tool(self, tool_call: ToolCallMessage):
        """
        调用工具并处理结果。

        参数:
            tool_call: 工具调用消息

        返回:
            bool: 是否需要进行早期返回
        """
        if self.agent.state == "waiting_user":
            self.agent.state = "working"

        if self.early_return:
            msg = f"工具调用被跳过: {tool_call.function_name}"
            self.agent.message_processor.append_message(RuntimeMessage(msg))
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

            await self.agent.lifecycle.trigger_tool_conflict(
                self.agent, tool_call, self.called_tools_in_round
            )
            logger.warning(conflict_msg)
            self.agent.message_processor.append_message(RuntimeMessage(conflict_msg))
            self.early_return = True
            return True

        self.called_tools_in_round.append(tool_call.function_name)

        compress_tools = [
            "compress_history_range",
            "mark_messages_as_garbage",
            "message_garbage_clean",
            "thanox_history",
        ]
        self.agent.compress_tool_called_in_last_response = (
            tool_call.function_name in compress_tools
        )

        should_block = await self.agent.lifecycle.trigger_before_tool_call(tool_call)
        if should_block:
            self.early_return = True
            return True

        result = await self._call_tool(tool_call)
        if result:
            self.early_return = True
        return result

    async def _call_tool(self, tool_call: ToolCallMessage) -> bool:
        """调用工具。"""
        try:
            tool_result = await self.tool_manager.process_tool_call(tool_call)

            from linhai.tool.base import ToolErrorMessage

            if isinstance(tool_result, ToolErrorMessage):
                await self.agent.lifecycle.trigger_tool_failure(
                    self.agent, tool_call, tool_result
                )
                msg = f"工具调用失败: {tool_result.content}"
                logger.error(msg)
                self.agent.message_processor.append_message(RuntimeMessage(msg))
                if tool_call.assert_success:
                    return True
                else:
                    return False

            await self.agent.lifecycle.trigger_tool_success(
                self.agent, tool_call, tool_result
            )

            replacement_message = await self.agent.lifecycle.trigger_after_tool_call(
                self.agent, tool_call, tool_result, True
            )
            if replacement_message is not None:
                tool_result = replacement_message

            await self._handle_tool_result(tool_call, tool_result)
            return False
        except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:

            await self.agent.lifecycle.trigger_tool_failure(self.agent, tool_call, e)
            msg = f"工具调用失败: {str(e)} {repr(e)}"
            logger.error(msg)
            self.agent.message_processor.append_message(RuntimeMessage(msg))
            return False

    async def _handle_tool_result(self, tool_call: ToolCallMessage, tool_result):
        """处理工具调用结果。"""

        tool_result_content = str(tool_result)
        if len(tool_result_content) > 8000:
            message_id = generate_id("largemessage")
            self.agent.large_messages[message_id] = tool_result
            self.agent.message_processor.append_message(
                RuntimeMessage(
                    f"为工具 {tool_call.function_name} 的消息分配了ID: {message_id}。"
                    "你可以在不需要此消息时使用 mark_messages_as_garbage 工具标记此消息为垃圾以节省token。"
                    + (
                        "注意：这个工具输出仍然远低于限制，仍然可以正常使用此工具，不要因为工具会输出较大内容就不使用工具！"
                        if len(tool_result_content) < 80000
                        else ""
                    )
                )
            )

        self.agent.message_processor.append_message(
            RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
        )
        self.agent.message_processor.append_message(tool_result)
        if self.agent.state == "waiting_user":
            self.agent.state = "working"
