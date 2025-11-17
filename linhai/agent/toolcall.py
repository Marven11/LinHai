"""工具调用处理模块，负责工具注册、调用和结果管理。"""

import logging
from typing import TYPE_CHECKING

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.tool.main import ToolManager
from linhai.llm import ToolCallMessage
from linhai.utils import generate_id
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
        
        # 工具管理器
        self.tool_manager: ToolManager = self.group_chat.get_members("tool_manager", ToolManager)
        
        # 工具确认配置
        tool_confirmation_config = self.context.get("tool_confirmation", {})
        self.skip_confirmation = tool_confirmation_config.get("skip_confirmation", False)
        self.whitelist = tool_confirmation_config.get("whitelist", [])
        self.timeout_seconds = tool_confirmation_config.get("timeout_seconds", 30)
        
        # 注册默认工具集
        self._register_default_toolsets()

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

    async def call_tool(self, tool_call: ToolCallMessage) -> bool:
        """
        调用工具并处理结果。

        参数:
            tool_call: 工具调用消息

        返回:
            bool: 是否需要进行早期返回
        """
        if self.agent.state == "waiting_user":
            self.agent.state = "working"

        # 统一设置compress_tool_called_in_last_response
        compress_tools = [
            "compress_history_range",
            "mark_messages_as_garbage",
            "message_garbage_clean",
            "thanox_history",
        ]
        self.agent.compress_tool_called_in_last_response = (
            tool_call.function_name in compress_tools
        )

        # 触发工具调用前的生命周期事件
        await self.agent.lifecycle.trigger_before_tool_call(tool_call)

        # 使用存储的tool_confirmation配置
        if self.skip_confirmation or tool_call.function_name in self.whitelist:
            return await self._call_tool_without_confirmation(tool_call)
        else:
            return await self._call_tool_with_confirmation(tool_call)

    async def _call_tool_without_confirmation(self, tool_call: ToolCallMessage) -> bool:
        """无需确认直接调用工具。"""
        try:
            tool_result = await self.tool_manager.process_tool_call(tool_call)

            # 检查工具结果，如果是ToolErrorMessage且assert_success为True，则中止
            from linhai.tool.base import ToolErrorMessage

            if (
                isinstance(tool_result, ToolErrorMessage)
                and tool_call.assert_success
            ):
                # 触发工具调用后的生命周期事件（失败）
                await self.agent.lifecycle.trigger_after_tool_call(
                    tool_call, tool_result, False
                )
                msg = f"工具调用失败: {tool_result.content}"
                logger.error(msg)
                self.agent.message_processor.get_messages().append(RuntimeMessage(msg))
                return True  # 需要早期返回，中止其他工具调用

            # 触发工具调用后的生命周期事件（成功）
            await self.agent.lifecycle.trigger_after_tool_call(
                tool_call, tool_result, True
            )

            # 处理工具结果
            await self._handle_tool_result(tool_call, tool_result)
            return False  # 不需要早期返回
        except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:
            # 触发工具调用后的生命周期事件（失败）
            await self.agent.lifecycle.trigger_after_tool_call(tool_call, e, False)
            msg = f"工具调用失败: {str(e)} {repr(e)}"
            logger.error(msg)
            self.agent.message_processor.get_messages().append(RuntimeMessage(msg))
            return False

    async def _call_tool_with_confirmation(self, tool_call: ToolCallMessage) -> bool:
        """需要用户确认的工具调用。"""
        from linhai.cli import CLIApp
        

        confirmation = await self.group_chat.get_members(
            "cli_app", CLIApp
        ).confirm_tool_request(tool_call)
        self.agent.message_processor.get_messages().append(
            RuntimeMessage(f"已发送工具调用请求: {tool_call.function_name}，等待用户确认...")
        )

        # 检查确认消息是否匹配当前工具调用
        if confirmation.tool_call.function_name != tool_call.function_name:
            self.agent.message_processor.get_messages().append(
                RuntimeMessage("错误：收到的确认消息不匹配当前工具调用")
            )
            return False

        # 根据确认状态执行或取消
        if confirmation.confirmed:
            try:
                tool_result = await self.tool_manager.process_tool_call(tool_call)
                await self._handle_tool_result(tool_call, tool_result)
                return False  # 不需要早期返回
            except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:
                msg = f"工具调用失败: {str(e)} {repr(e)}"
                logger.error(msg)
                self.agent.message_processor.get_messages().append(RuntimeMessage(msg))
                return False
        else:
            self.agent.message_processor.get_messages().append(
                RuntimeMessage(f"用户取消了工具调用: {tool_call.function_name}")
            )
            return False

    async def _handle_tool_result(self, tool_call: ToolCallMessage, tool_result):
        """处理工具调用结果。"""

        # 检查工具结果大小，如果大于8000字符则记录ID
        tool_result_content = str(tool_result)
        if len(tool_result_content) > 8000:
            message_id = generate_id("largemessage")
            self.agent.large_messages[message_id] = tool_result
            self.agent.message_processor.get_messages().append(
                RuntimeMessage(
                    f"工具 {tool_call.function_name} 返回的内容较大（{len(tool_result_content)} 字符），已分配ID: {message_id}。"
                    "你可以使用 mark_messages_as_garbage 工具标记此消息为垃圾以节省token。"
                )
            )

        self.agent.message_processor.get_messages().append(
            RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
        )
        self.agent.message_processor.get_messages().append(tool_result)
        if self.agent.state == "waiting_user":
            self.agent.state = "working"