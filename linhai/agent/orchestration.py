"""
消息编排模块，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。
"""

import random
import time
import asyncio
from typing import Optional, TYPE_CHECKING, Literal

from linhai.agent.workflow import compress_context_range
from linhai.llm import ToolCallMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.utils import generate_id, CliRuntimeNotice
from linhai.type_hints import ThresholdInfo
from .base import Message, RuntimeMessage
from .message import AgentMessage

if TYPE_CHECKING:
    from .main import Agent


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
        # 注册到group chat以便其他组件可以访问
        self.group_chat.register_member("agent_context_orchestration", self)

        self.large_messages: dict[str, Message] = {}
        self.garbage_message_ids: set[str] = set()
        self.last_threshold_state: Optional[str] = None
        self.last_compress_or_clean_time: Optional[float] = None

        self._register_lifecycle_callbacks()

    def mark_messages_as_garbage(self, message_ids: list[str]) -> str:
        """将多个消息标记为垃圾消息。

        Args:
            message_ids: 要标记为垃圾的消息ID列表

        Returns:
            标记结果消息
        """
        marked_ids = []
        not_found_ids = []
        already_marked_ids = []

        for message_id in message_ids:
            # 检查消息是否存在
            if message_id not in self.large_messages:
                not_found_ids.append(message_id)
                continue

            # 检查是否已标记
            if message_id in self.garbage_message_ids:
                already_marked_ids.append(message_id)
                continue

            # 标记为垃圾
            self.garbage_message_ids.add(message_id)
            marked_ids.append(message_id)

        # 构建结果消息
        result_parts = []
        if marked_ids:
            result_parts.append(f"已成功标记 {len(marked_ids)} 条消息为垃圾消息")
            result_parts.append(f"ID为{', '.join(marked_ids)}的消息已被标记为垃圾")
        if not_found_ids:
            result_parts.append(f"以下ID不存在: {', '.join(not_found_ids)}")
        if already_marked_ids:
            result_parts.append(f"以下ID已被重复标记: {', '.join(already_marked_ids)}")

        return "; ".join(result_parts) if result_parts else "没有消息被标记"

    async def context_garbage_clean(self) -> str:
        """清理所有已标记为垃圾的消息。

        Returns:
            清理结果消息
        """
        await self.agent_message.count_invalidate_cache()
        if not self.garbage_message_ids:
            return "没有垃圾消息需要清理"

        # 获取当前所有垃圾消息ID的快照
        garbage_snapshot = set(self.garbage_message_ids)
        removed_count = 0
        invalid_count = 0

        for message_id in garbage_snapshot:
            if message_id in self.large_messages:
                msg = self.large_messages.pop(message_id)
                await self.agent_message.remove_message(msg)
                removed_count += 1
            else:
                invalid_count += 1
            # 无论消息是否存在，都从垃圾集合中移除
            self.garbage_message_ids.discard(message_id)

        self.last_compress_or_clean_time = time.time()
        return f"已清理 {removed_count} 条消息"

    def record_large_message(self, message: Message, content: str) -> str:
        """记录大消息并返回ID。

        Args:
            message: 大消息对象
            content: 消息内容

        Returns:
            分配的消息ID
        """
        message_id = generate_id("largemessage")
        self.large_messages[message_id] = message
        return message_id

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
    ) -> None:
        """添加软限制消息提示。

        Args:
            threshold_info: 阈值信息
        """
        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])

        if current_state == "绿灯" and self.last_threshold_state == "绿灯":
            return

        self.last_threshold_state = current_state
        message_content = self._build_threshold_message(
            current_state,
            threshold_info["hard_limit"],
            threshold_info["used_tokens"],
            threshold_info["usage_ratio"],
        )
        self.agent_message.append_message(RuntimeMessage(message_content))

    async def check_and_handle_threshold(self, agent: "Agent") -> None:
        """检查阈值并处理相应的通知和操作引导。

        Args:
            agent: Agent实例，用于获取阈值信息和token使用量
        """
        # 从agent获取阈值信息
        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        # 添加软限制通知
        self.add_soft_threshold_notification(threshold_info)

        # 根据状态提供操作引导
        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])

        # 检查一分钟内是否调用过消息清理工具
        recently_called_cleanup = self._recently_called_cleanup_tool()

        # 根据状态提供相应的操作引导
        if current_state == "红灯":
            await self._handle_red_state(recently_called_cleanup, threshold_info)
        elif current_state == "黄灯":
            self._handle_yellow_state(recently_called_cleanup)
        elif current_state in ["绿灯", "绿灯闪烁"]:
            self._handle_green_state(current_state, recently_called_cleanup)

    def _recently_called_cleanup_tool(self) -> bool:
        """检查一分钟内是否调用过消息清理工具。

        Returns:
            bool: 如果一分钟内调用过消息清理工具返回True，否则返回False
        """
        if not self.last_compress_or_clean_time:
            return False
        time_since_last_cleanup = time.time() - self.last_compress_or_clean_time
        return time_since_last_cleanup < 60

    def _determine_tool_category(self, tool_name: str) -> Literal["cleanup", "management", "other"]:
        """判断工具所属类别。

        Returns:
            str: 工具类别，可能的值为：
                "cleanup" - 消息清理工具
                "management" - 其他消息管理工具
                "other" - 其他工具
        """
        # 消息清理工具
        if tool_name in ["compress_context_range", "context_garbage_clean", "context_thanox"]:
            return "cleanup"
        # 其他消息管理工具
        elif tool_name == "mark_messages_as_garbage":
            return "management"
        # 其他工具
        else:
            return "other"

    def should_block_tool_call(self, tool_name: str, threshold_info: ThresholdInfo | None) -> bool:
        """判断是否应该拦截工具调用。

        Args:
            tool_name: 工具名称
            threshold_info: 阈值信息，如果为None则不拦截

        Returns:
            bool: 如果应该拦截返回True，否则返回False
        """
        if threshold_info is None:
            return False

        current_state = self._determine_threshold_state(threshold_info["usage_ratio"])
        recently_called_cleanup = self._recently_called_cleanup_tool()
        tool_category = self._determine_tool_category(tool_name)

        # 如果最近调用过消息清理工具：禁止使用消息清理工具，可以使用其他消息管理工具和其他工具
        if recently_called_cleanup:
            return tool_category == "cleanup"
        
        # 如果最近没有调用过消息清理工具且为红灯：只能调用消息清理工具和其他消息管理工具，禁止调用其他工具
        if current_state == "红灯":
            return tool_category not in ["cleanup", "management"]
        
        # 其他状态: 可以调用任何工具
        return False

    async def _handle_red_state(self, recently_called_cleanup: bool, threshold_info: ThresholdInfo) -> None:
        """处理红灯状态。"""
        assert threshold_info is not None, "threshold_info should not be None in red state"
        
        if not recently_called_cleanup:
            await self._handle_red_state_no_recent_cleanup(threshold_info)
        else:
            self._handle_red_state_recent_cleanup()
    
    async def _handle_red_state_no_recent_cleanup(self, threshold_info: ThresholdInfo) -> None:
        """处理红灯状态且最近没有调用清理工具的情况。"""
        hard_limit = threshold_info["hard_limit"]
        used_tokens = threshold_info["used_tokens"]
        if used_tokens >= hard_limit:
            await self.context_thanox()
            self.agent_message.append_message(
                RuntimeMessage(
                    f"当前Token用量{used_tokens}已超过硬限制{hard_limit}，已自动调用context_thanox删除一半消息。"
                )
            )
            return
        
        guidance_message = (
            "当前处于红灯状态，建议调用compress_context_range、context_garbage_clean或context_thanox等消息清理工具。"
        )
        self.agent_message.append_message(RuntimeMessage(guidance_message))
    
    def _handle_red_state_recent_cleanup(self) -> None:
        """处理红灯状态且最近调用过清理工具的情况。"""
        if self.large_messages:
            large_message_ids = list(self.large_messages.keys())[:3]
            guidance_message = (
                f"一分钟内已调用过历史压缩或清理，禁止使用消息清理工具，但可以使用其他工具。"
                f"当前有{len(self.large_messages)}条大消息，"
                f"可以先用mark_messages_as_garbage工具标记ID为{', '.join(large_message_ids)}的消息为垃圾。"
            )
            self.agent_message.append_message(RuntimeMessage(guidance_message))
        else:
            guidance_message = "一分钟内已调用过历史压缩或清理，禁止使用消息清理工具，但可以使用其他工具正常进行工作！"
            self.agent_message.append_message(RuntimeMessage(guidance_message))

    def _handle_yellow_state(self, recently_called_cleanup: bool) -> None:
        """处理黄灯状态。"""
        if not recently_called_cleanup and self.garbage_message_ids:
            # 黄灯状态：引导清理垃圾消息
            guidance_message = "当前有垃圾消息需要清理，建议调用context_garbage_clean工具清理垃圾消息。"
            self.agent_message.append_message(RuntimeMessage(guidance_message))

    def _handle_green_state(self, current_state: str, recently_called_cleanup: bool) -> None:
        """处理绿灯和绿灯闪烁状态。"""
        # 绿灯和绿灯闪烁状态：引导标记消息
        if self.large_messages:
            # 如果有大消息，引导标记大消息
            large_message_ids = list(self.large_messages.keys())[:3]
            guidance_message = (
                f"当前有{len(self.large_messages)}条大消息，"
                f"建议使用mark_messages_as_garbage工具标记ID为{', '.join(large_message_ids)}的消息为垃圾。"
            )
            self.agent_message.append_message(RuntimeMessage(guidance_message))
        else:
            # 如果没有大消息，引导标记不需要的消息
            guidance_message = (
                f"当前处于{current_state}状态，建议标记不需要的消息为垃圾以节省token。"
            )
            self.agent_message.append_message(RuntimeMessage(guidance_message))

    def _determine_threshold_state(self, usage_ratio: float) -> str:
        # usage_ratio是小数比例（0-1），转换为百分比（0-100）进行比较
        percentage = usage_ratio * 100
        if percentage < 50:
            return "绿灯"
        elif 50 <= percentage < 70:
            return "绿灯闪烁"
        elif 70 <= percentage < 90:
            return "黄灯"
        else:
            return "红灯"

    def _build_threshold_message(
        self, current_state: str, hard_limit: int, used_tokens: int, usage_ratio: float
    ) -> str:
        message_count = len(self.agent_message.messages)
        percentage = usage_ratio * 100

        # 绿灯、绿灯闪烁、黄灯状态的消息模板
        if current_state == "绿灯":
            return (
                f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
                f"当前使用{percentage:.1f}%（绿灯状态）。"
                f"当前已有{message_count}条消息。"
                "可以顺手标记大消息，无需担心token限制。"
            )

        if current_state == "绿灯闪烁":
            return (
                f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
                f"当前使用{percentage:.1f}%（绿灯闪烁状态）。"
                f"当前已有{message_count}条消息。"
                "应该积极标记大消息，可以顺手删除一些实在和当前任务无关的消息。"
            )

        if current_state == "黄灯":
            return (
                f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
                f"当前使用{percentage:.1f}%（黄灯状态）。"
                f"当前已有{message_count}条消息。"
                "积极考虑删除和当前任务无关的消息，也可以使用历史压缩删除之前任务的消息。"
            )

        # 红灯状态
        large_messages_info = ""
        if self.large_messages:
            large_message_ids = list(self.large_messages.keys())[:3]
            large_messages_info = (
                f"当前已有{len(self.large_messages)}条大消息。"
                f"前3个大消息ID: {', '.join(large_message_ids)}。"
            )

        garbage_count = len(self.garbage_message_ids)
        recently_called_cleanup = self._recently_called_cleanup_tool()
        
        if recently_called_cleanup:
            action_guide = "一分钟内已调用过消息清理工具，可以正常进行工作！"
        elif garbage_count >= 5:
            action_guide = "当前有至少5条垃圾消息，建议调用context_garbage_clean清理垃圾消息。"
        else:
            action_guide = "建议调用compress_context_range删除大约一半消息！"

        return (
            f"当前Token用量为{used_tokens}，硬限制为{hard_limit}，"
            f"当前使用{percentage:.1f}%（红灯状态）。"
            f"当前已有{message_count}条消息。"
            f"{large_messages_info}{action_guide}"
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
        garbage_count = len(self.garbage_message_ids)

        pieces = []
        if use_nerd_font:
            pieces.append(f"\uf27a {message_count}")
            if large_count > 0:
                pieces.append(f"\uf1c0 {large_count}")
            if garbage_count > 0:
                pieces.append(f"\uea81 {garbage_count}")
        else:
            pieces.append(f"{message_count} msgs")
            if large_count > 0:
                pieces.append(f"{large_count} large")
            if garbage_count > 0:
                pieces.append(f"{garbage_count} garbage")

        return pieces

    def get_message_management_toolset(self) -> "ToolSet":
        """获取消息管理工具集。

        Returns:
            包含消息管理工具的ToolSet
        """

        toolset = ToolSet()

        @toolset.register_tool(
            name="mark_messages_as_garbage",
            desc="将多个消息标记为不需要的垃圾消息。在绿灯、绿闪、黄灯时优先使用此工具标记消息。"
            "这个工具可以安全地和其他工具一起调用，不会冲突，但是需要注意在其他工具调用完成后再标记",
            args={
                "ids": ToolArgInfo(desc="要标记为垃圾的消息的ID", type="list[str]"),
            },
            required_args=["ids"],
        )
        def mark_messages_as_garbage(ids: list[str]) -> str:
            return self.mark_messages_as_garbage(ids)

        @toolset.register_tool(
            name="context_garbage_clean",
            desc="清理已经标记的垃圾消息。",
            args={},
            required_args=[],
        )
        async def context_garbage_clean_tool() -> str:
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
        from linhai.tool.base import ToolSet

        toolset = ToolSet()

        @toolset.register_tool(
            name="compress_context_range",
            desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            args={},
            required_args=[],
        )
        async def compress_context_range_tool() -> str:
            from linhai.agent import Agent
            agent = self.group_chat.get_members("agent", Agent)
            result = await compress_context_range(agent)
            self.last_compress_or_clean_time = time.time()
            return result

        return toolset

    def _register_lifecycle_callbacks(self) -> None:
        """注册生命周期回调。"""
        from .lifecycle import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_after_working(self._on_after_working)
        lifecycle.register_after_tool_call(self._on_after_tool_call)

    async def _on_after_working(self, _agent: "Agent") -> None:
        """工作完成后的回调，重置状态。"""
        # 重置状态，例如清除大消息记录或垃圾消息ID
        self.large_messages.clear()
        self.garbage_message_ids.clear()
        self.last_threshold_state = None

    async def _on_after_tool_call(
        self,
        _agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: str,
        _success: bool,
    ) -> Optional[RuntimeMessage]:
        tool_result_content = str(tool_result)
        if len(tool_result_content) > 3000:
            # 创建RuntimeMessage来包装工具结果
            result_message = RuntimeMessage(tool_result_content)
            message_id = self.record_large_message(result_message, tool_result_content)
            self.agent_message.append_message(
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




class RedStateToolBlockPlugin:
    """红灯状态工具调用拦截插件。

    在红灯状态且一分钟内没有调用过消息清理类工具时禁止调用其他工具。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.CLEANUP_TOOLS = {
            "compress_context_range",
            "context_garbage_clean",
            "context_thanox",
        }
        self.MANAGEMENT_TOOLS = {
            "mark_messages_as_garbage",
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
        if agent is None:
            return False
        
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )
        if orchestration is None:
            return False

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return False

        # 使用orchestration的方法判断是否应该拦截
        should_block = orchestration.should_block_tool_call(
            tool_call.function_name, threshold_info
        )

        if should_block:
            error_msg = (
                f"错误：当前处于红灯状态（token使用率{threshold_info['usage_ratio']*100:.1f}%），"
                f"禁止调用{tool_call.function_name}工具！"
                "红灯状态下只允许调用compress_context_range、context_garbage_clean、"
                "context_thanox或mark_messages_as_garbage等消息管理工具。"
            )

            # 添加错误消息到agent
            agent.message_processor.append_message(RuntimeMessage(error_msg))
            await self.group_chat.send_if_exists(
                "ui_log",
                CliRuntimeNotice(
                    level="WARNING",
                    content=f"红灯状态下阻止调用{tool_call.function_name}工具，请先调用消息清理类工具",
                ),
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

    async def after_message_generation(
        self,
        _answer: dict,
        _full_response: str,
        _tool_calls: list[dict],
    ) -> None:
        """在消息生成后添加appending message。"""
        from .main import Agent
        agent = self.group_chat.get_members("agent", Agent)
        if agent is None:
            return

        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )
        if orchestration is None:
            return

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return

        # 添加阈值通知（这原本在AgentContextOrchestration.add_soft_threshold_notification中）
        orchestration.add_soft_threshold_notification(threshold_info)

    def register(self, lifecycle):
        """注册插件回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
