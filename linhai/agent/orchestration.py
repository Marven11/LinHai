"""
消息编排模块，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。
"""

import random
import time
import reprlib
from typing import Optional, Literal, TypedDict

from linhai.agent.workflow import context_range_compress
from linhai.llm import ToolCallMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolResultMessage, ToolErrorMessage
from linhai.utils import CliRuntimeNotice
from linhai.type_hints import ThresholdInfo
from .base import Message, RuntimeMessage
from .message import AgentMessage

r = reprlib.Repr()
r.maxstring = 100


class ToolBlockDetailsDict(TypedDict):
    blocked_category: str | None
    actual_category: str
    recently_called_cleanup: bool
    current_state: str


class AgentContextOrchestration:
    """消息编排器，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。"""

    def __init__(self, group_chat: GroupChat, agent_message: AgentMessage):
        """初始化消息编排器。

        Args:
            group_chat: GroupChat实例
            agent_message: 基础消息管理器实例
        """
        self.group_chat = group_chat
        self.agent_message = agent_message
        self.group_chat.register_member("agent_context_orchestration", self)

        self.large_messages: set[Message] = set()
        self.last_threshold_state: Optional[str] = None
        self.last_compress_or_clean_time: Optional[float] = None

        self._register_lifecycle_callbacks()

    def get_large_message_reprs(self, limit: int = 3) -> list[str]:
        """获取大消息repr列表。

        Args:
            limit: 返回的最大数量

        Returns:
            大消息repr列表
        """

        reprs = [r.repr(msg) for msg in list(self.large_messages)[:limit]]
        return reprs

    async def context_garbage_clean(self) -> ToolResultMessage | ToolErrorMessage:
        """清理所有大消息。

        Returns:
            清理结果消息。如果当前大消息少于5条则返回失败消息。
        """
        if len(self.large_messages) < 5:
            error_msg = f"错误：当前只有{len(self.large_messages)}条大消息，需要至少5条大消息才能清理"
            return ToolErrorMessage(error_msg)

        await self.agent_message.count_invalidate_cache()
        removed_messages = []

        for message in self.large_messages:
            await self.agent_message.remove_message(message)
            removed_messages.append(r.repr(str(message)))

        self.large_messages.clear()
        self.last_compress_or_clean_time = time.time()

        result_lines = [f"已清理 {len(removed_messages)} 条大消息:"]
        result_lines.extend(removed_messages)
        return ToolResultMessage("\n".join(result_lines))

    async def context_thanox(self) -> str:
        """随机删除一半消息（不包括前5条系统消息）。

        Returns:
            str: 删除结果消息
        """
        messages = self.agent_message.messages
        if len(messages) <= 10:
            return "消息数量不足，无需删除"

        await self.agent_message.count_invalidate_cache()
        indices_to_delete = random.sample(range(5, len(messages)), len(messages) // 2)

        await self.agent_message.replace_messages(
            [msg for idx, msg in enumerate(messages) if idx not in indices_to_delete]
        )
        self.last_compress_or_clean_time = time.time()
        return f"context_thanox: 随机删除了{len(indices_to_delete)}条消息"

    def add_soft_threshold_notification(
        self,
        threshold_info: ThresholdInfo,
    ) -> Optional[str]:
        """添加软限制消息提示。

        Args:
            threshold_info: 阈值信息
        """
        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])

        if current_state == "绿灯" and self.last_threshold_state == "绿灯":
            return None

        self.last_threshold_state = current_state
        message_content = self._build_threshold_message(
            current_state,
            threshold_info["hard_limit"],
            threshold_info["used_tokens"],
            threshold_info["usage_ratio"],
        )
        return message_content

    async def check_and_handle_threshold(self, agent: "Agent") -> None:
        """检查阈值并处理相应的通知和操作引导。

        Args:
            agent: Agent实例，用于获取阈值信息和token使用量
        """
        # 从agent获取阈值信息（用于判断当前token使用状态）
        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])

        recently_called_cleanup = self._recently_called_cleanup_tool()

        if current_state == "红灯" and not recently_called_cleanup:
            hard_limit = threshold_info["hard_limit"]
            used_tokens = threshold_info["used_tokens"]
            if used_tokens >= hard_limit:
                await self.context_thanox()

    def _recently_called_cleanup_tool(self) -> bool:
        """检查一分钟内是否调用过消息清理工具。

        Returns:
            bool: 如果一分钟内调用过消息清理工具返回True，否则返回False
        """
        if not self.last_compress_or_clean_time:
            return False
        time_since_last_cleanup = time.time() - self.last_compress_or_clean_time
        return time_since_last_cleanup < 60

    def _determine_tool_category(self, tool_name: str) -> Literal["cleanup", "other"]:
        """判断工具所属类别。

        Returns:
            str: 工具类别，可能的值为：
                "cleanup" - 消息清理工具
                "other" - 其他工具
        """
        if tool_name in {
            "context_range_compress",
            "context_garbage_clean",
            "context_thanox",
        }:
            return "cleanup"

        else:
            return "other"

    def get_tool_block_details(
        self, tool_name: str, threshold_info: ThresholdInfo | None
    ) -> ToolBlockDetailsDict:
        """获取工具拦截的详细信息。

        Args:
            tool_name: 工具名称
            threshold_info: 阈值信息，如果为None则不拦截

        Returns:
            包含以下键的字典：
                blocked_category: str | None, 应该拦截的工具类别，None表示不拦截
                actual_category: str, 当前工具的实际类别 ("cleanup", "other")
                recently_called_cleanup: bool, 最近是否调用过清理工具
                current_state: str, 当前阈值状态
        """
        if threshold_info is None:
            return {
                "blocked_category": None,
                "actual_category": "other",
                "recently_called_cleanup": False,
                "current_state": "绿灯",
            }

        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])
        recently_called_cleanup = self._recently_called_cleanup_tool()
        actual_category = self._determine_tool_category(tool_name)

        # 直接根据状态和工具类别判断blocked_category
        if current_state == "红灯":
            if recently_called_cleanup:
                # 红灯状态，最近调用过清理，只阻塞清理工具
                blocked_category = "cleanup"
            else:
                # 红灯状态，没有调用过清理，只阻塞其他工具（允许清理工具）
                blocked_category = "other"
        else:  # 绿灯或黄灯状态
            if recently_called_cleanup:
                # 非红灯状态，最近调用过清理，只阻塞清理工具
                blocked_category = "cleanup"
            else:
                # 非红灯状态，没有调用过清理，不阻塞任何工具
                blocked_category = None

        return {
            "blocked_category": blocked_category,
            "actual_category": actual_category,
            "recently_called_cleanup": recently_called_cleanup,
            "current_state": current_state,
        }

    def _determine_threshold_state(self, usage_ratio: float) -> str:
        percentage = usage_ratio * 100
        if percentage < 70:
            return "绿灯"
        elif 70 <= percentage < 90:
            return "黄灯"
        else:
            return "红灯"

    def _build_threshold_message(
        self, current_state: str, hard_limit: int, used_tokens: int, usage_ratio: float
    ) -> str:
        message_count = len(self.agent_message.messages)
        percentage = usage_ratio * 100

        # 绿灯、黄灯状态的消息模板（提供不同状态的提示信息）
        if current_state == "绿灯":
            return (
                f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
                f"当前使用{percentage:.1f}%（绿灯状态）。"
                f"当前已有{message_count}条消息。"
            )

        if current_state == "黄灯":
            large_count = len(self.large_messages)
            return (
                f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
                f"当前使用{percentage:.1f}%（黄灯状态）。"
                f"当前已有{message_count}条消息，其中有{large_count}条大消息。"
                "黄灯状态下需要避免读取文件，直接开始修改需要修改的文件。"
                "积极考虑调用context_garbage_clean清理大消息。"
            )

        large_count = len(self.large_messages)
        recently_called_cleanup = self._recently_called_cleanup_tool()

        if recently_called_cleanup:
            action_guide = "一分钟内已调用过消息清理工具，可以正常进行工作！"
        elif large_count >= 5:
            action_guide = f"当前有至少{large_count}条大消息，建议调用context_garbage_clean清理大消息。"
        else:
            action_guide = "建议调用context_range_compress删除大约一半消息！"

        return (
            f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
            f"当前使用{percentage:.1f}%（红灯状态）。"
            f"当前已有{message_count}条消息。" + action_guide
        )

    def get_status_display_pieces(self, use_nerd_font: bool = False) -> list[str]:
        """获取状态显示片段列表，用于CLI底栏。

        Args:
            use_nerd_font: 是否使用nerd font符号

        Returns:
            状态显示片段列表，每个片段是一个独立的显示单元
        """
        message_count = len(self.agent_message.messages)
        large_count = len(self.large_messages)

        pieces = []
        if use_nerd_font:
            pieces.append(f"\uf27a {message_count}")
            if large_count > 0:
                pieces.append(f"\uf1c0 {large_count}")
        else:
            pieces.append(f"{message_count} msgs")
            if large_count > 0:
                pieces.append(f"{large_count} large")

        return pieces

    def get_message_management_toolset(self) -> "ToolSet":
        """获取消息管理工具集。

        Returns:
            包含消息管理工具的ToolSet
        """

        toolset = ToolSet()

        @toolset.register_tool(
            name="context_garbage_clean",
            desc="清理大消息：如果当前有至少5条大消息，全部删除并返回每条被删除的消息的repr。",
            args={},
            required_args=[],
        )
        async def context_garbage_clean_tool() -> ToolErrorMessage | ToolResultMessage:
            # 记录工具调用时间用于后续判断
            self.last_compress_or_clean_time = time.time()
            return await self.context_garbage_clean()

        @toolset.register_tool(
            name="context_thanox",
            desc="随机删除一半消息（不包括前5条系统消息）。",
            args={},
            required_args=[],
        )
        async def context_thanox_tool() -> str:
            # 记录工具调用时间用于后续判断
            self.last_compress_or_clean_time = time.time()
            return await self.context_thanox()

        return toolset

    def get_workflow_toolset(self) -> "ToolSet":
        """获取工作流工具集。

        Returns:
            包含工作流工具的ToolSet
        """

        toolset = ToolSet()

        @toolset.register_tool(
            name="context_range_compress",
            desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            args={},
            required_args=[],
        )
        async def context_range_compress_tool() -> str:
            from linhai.agent import Agent

            agent = self.group_chat.get_members("agent", Agent)
            result = await context_range_compress(agent)
            self.last_compress_or_clean_time = time.time()
            return result

        return toolset

    def _register_lifecycle_callbacks(self) -> None:
        """注册生命周期回调。"""
        from .lifecycle import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_after_working(self._on_after_working)
        lifecycle.register_after_tool_call(self._on_after_tool_call)

        # 注册大消息数量通知插件
        large_message_plugin = LargeMessageCountPlugin(self.group_chat)
        large_message_plugin.register(lifecycle)

    async def _on_after_working(self, _agent: "Agent") -> None:
        """工作完成后的回调，重置状态。"""
        # 重置状态，例如清除大消息记录或垃圾消息ID
        self.large_messages.clear()
        self.last_threshold_state = None

    async def _on_after_tool_call(
        self,
        _agent: "Agent",
        _tool_call: ToolCallMessage,
        tool_result_msg: ToolResultMessage,
        _success: bool,
    ) -> Optional[RuntimeMessage]:
        tool_result_content = str(tool_result_msg)
        if len(tool_result_content) > 3000:
            self.large_messages.add(tool_result_msg)


class RedStateToolBlockPlugin:
    """红灯状态工具调用拦截插件。

    在红灯状态且一分钟内没有调用过消息清理类工具时禁止调用其他工具。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.CLEANUP_TOOLS = {
            "context_range_compress",
            "context_garbage_clean",
            "context_thanox",
        }

    async def before_tool_call(
        self,
        tool_call: ToolCallMessage,
    ) -> bool:
        """在工具调用前检查是否需要拦截。

        Returns:
            bool: 如果应该拦截返回True，否则返回False
        """
        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return False

        if orchestration is None:
            return False

        # 使用orchestration的方法获取工具拦截详情
        details = orchestration.get_tool_block_details(
            tool_call.function_name, threshold_info
        )

        if details["blocked_category"] == details["actual_category"]:
            recently_called_cleanup = details["recently_called_cleanup"]
            current_state = details["current_state"]

            if details["blocked_category"] == "cleanup" and recently_called_cleanup:
                error_msg = f"一分钟内已经调用过消息清理工具，禁止调用{tool_call.function_name}工具"
                ui_msg = f"一分钟内已调用过消息清理工具，禁止调用{tool_call.function_name}工具"
            else:
                error_msg = (
                    f"错误：当前处于{current_state}状态（token使用率{threshold_info['usage_ratio']*100:.1f}%），"
                    f"禁止调用{tool_call.function_name}工具！"
                    "红灯状态下只允许调用消息管理工具。"
                )
                ui_msg = f"{current_state}状态下阻止调用{tool_call.function_name}工具，请先调用消息清理类工具"

            # 添加错误消息到agent
            await agent.interrupt(error_msg)
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(level="WARNING", content=ui_msg),
            )
            return True

        return False

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)


class AppendingMessagePlugin:
    """添加appending message的插件。

    将添加appending message的实现拆分成一个新的plugin类。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def before_message_generation(
        self,
        _enable_compress: bool,
        _disable_waiting_user_warning: bool,
    ) -> None:
        """在消息生成前添加appending message。"""
        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        if orchestration is None:
            return

        message_content = orchestration.add_soft_threshold_notification(threshold_info)
        if message_content is not None:
            agent.message_processor.update_appending_message(
                RuntimeMessage(message_content), source="threshold_notification"
            )

    async def after_message_generation(
        self,
        _answer: dict,
        _full_response: str,
        _tool_calls: list[dict],
    ) -> None:
        """在消息生成后添加appending message。"""
        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        if orchestration is None:
            return

        message_content = orchestration.add_soft_threshold_notification(threshold_info)
        if message_content is not None:
            agent.message_processor.update_appending_message(
                RuntimeMessage(message_content), source="threshold_notification"
            )

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
        lifecycle.register_after_message_generation(self.after_message_generation)


class LargeMessageCountPlugin:
    """大消息数量通知插件。

    在before_message_generation中更新appending_message，告知当前有几条大消息。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def before_message_generation(
        self,
        _enable_compress: bool,
        _disable_waiting_user_warning: bool,
    ) -> None:
        """在消息生成前添加大消息数量通知。"""
        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        if orchestration is None:
            return

        large_count = len(orchestration.large_messages)
        if large_count > 0:
            message_content = f"当前有{large_count}条大消息，建议积极考虑调用context_garbage_clean清理大消息。"
            agent.message_processor.update_appending_message(
                RuntimeMessage(message_content), source="large_message_count"
            )

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
