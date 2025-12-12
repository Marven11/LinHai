"""消息编排模块，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。"""

import random
import time
from typing import Optional, TYPE_CHECKING, Any

from linhai.agent.workflow import compress_history_range
from linhai.llm import ToolCallMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.utils import generate_id
from .base import Message, RuntimeMessage
from .message import AgentMessage

if TYPE_CHECKING:
    from linhai.agent import Agent


class AgentMessageOrchestration:
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
        self.group_chat.register_member("agent_message_orchestration", self)

        self.large_messages: dict[str, Message] = {}
        self.garbage_message_ids: set[str] = set()
        self.last_threshold_state: Optional[str] = None
        self.compress_tool_called_in_last_response: bool = False
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

    async def message_garbage_clean(self) -> str:
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

    async def thanox_history(self) -> str:
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
        return f"thanox_history: 随机删除了{len(indices_to_delete)}条消息"

    def set_compress_tool_called(self, called: bool) -> None:
        """设置压缩工具调用状态。

        Args:
            called: 是否调用了压缩工具
        """
        self.compress_tool_called_in_last_response = called

    def add_soft_threshold_notification(
        self,
        threshold_info: tuple[int, int, int, float],
    ) -> None:
        """添加软限制消息提示。

        Args:
            threshold_info: 阈值信息元组 (hard, used, remaining, taken)
        """
        if self.compress_tool_called_in_last_response:
            return

        hard, used, _remaining, taken = threshold_info
        current_state = self._determine_threshold_state(taken)

        if current_state == "绿灯" and self.last_threshold_state == "绿灯":
            return

        self.last_threshold_state = current_state
        message_content = self._build_threshold_message(
            current_state, hard, used, taken
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
        # threshold_info是4元组: (hard, used, remaining, taken)
        hard, used, _remaining, taken = threshold_info
        current_state = self._determine_threshold_state(taken)

        # 检查一分钟内是否调用过历史压缩或清理垃圾消息
        can_compress_or_clean = self._can_compress_or_clean()

        # 如果已经在上一个响应中调用了压缩工具，则跳过
        if self.compress_tool_called_in_last_response:
            # 即使压缩工具已被调用，仍应为黄灯和绿灯状态提供引导
            if (
                current_state == "黄灯"
                and can_compress_or_clean
                and self.garbage_message_ids
            ):
                self._handle_yellow_state(can_compress_or_clean)
            elif current_state in ["绿灯", "绿灯闪烁"] and self.large_messages:
                self._handle_green_state(current_state)
            return

        # 根据状态提供相应的操作引导
        if current_state == "红灯":
            self._handle_red_state(can_compress_or_clean)
        elif current_state == "黄灯":
            self._handle_yellow_state(can_compress_or_clean)
        elif current_state in ["绿灯", "绿灯闪烁"]:
            self._handle_green_state(current_state)

    def _can_compress_or_clean(self) -> bool:
        """检查一分钟内是否调用过历史压缩或清理垃圾消息。

        Returns:
            bool: 如果可以压缩或清理返回True，否则返回False
        """
        if not self.last_compress_or_clean_time:
            return True
        time_since_last_compress_or_clean = (
            time.time() - self.last_compress_or_clean_time
        )
        return time_since_last_compress_or_clean >= 60

    def _handle_red_state(self, can_compress_or_clean: bool) -> None:
        """处理红灯状态。"""
        if can_compress_or_clean:
            # 引导agent调用压缩工具
            guidance_message = (
                "当前消息过多，建议调用compress_history_range工具进行历史压缩。"
            )
            self.agent_message.append_message(RuntimeMessage(guidance_message))
            # 设置压缩工具调用标志
            self.compress_tool_called_in_last_response = True
        else:
            # 一分钟内已调用过压缩或清理，不设置压缩工具调用标志
            # 但可以标记大消息为垃圾
            if self.large_messages:
                large_message_ids = list(self.large_messages.keys())[:3]
                guidance_message = (
                    f"一分钟内已调用过历史压缩或清理，现在不需要担心消息长度问题！正常进行工作！"
                    f"当前有{len(self.large_messages)}条大消息，"
                    f"可以先用mark_messages_as_garbage工具标记ID为{', '.join(large_message_ids)}的消息为垃圾。"
                )
                self.agent_message.append_message(RuntimeMessage(guidance_message))
            else:
                # 没有大消息，引导等待
                guidance_message = "一分钟内已调用过历史压缩或清理，现在不需要担心消息长度问题！正常进行工作！"
                self.agent_message.append_message(RuntimeMessage(guidance_message))

    def _handle_yellow_state(self, can_compress_or_clean: bool) -> None:
        """处理黄灯状态。"""
        if can_compress_or_clean and self.garbage_message_ids:
            # 黄灯状态：引导清理垃圾消息
            guidance_message = "当前有垃圾消息需要清理，建议调用message_garbage_clean工具清理垃圾消息。"
            self.agent_message.append_message(RuntimeMessage(guidance_message))

    def _handle_green_state(self, current_state: str) -> None:
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

    def _determine_threshold_state(self, taken: float) -> str:
        # taken是小数比例（0-1），转换为百分比（0-100）进行比较
        percentage = taken * 100
        if percentage < 50:
            return "绿灯"
        elif 50 <= percentage < 70:
            return "绿灯闪烁"
        elif 70 <= percentage < 90:
            return "黄灯"
        else:
            return "红灯"

    def _build_threshold_message(
        self, current_state: str, hard: int, used: int, taken: float
    ) -> str:
        message_count = len(self.agent_message.messages)

        # 绿灯、绿灯闪烁、黄灯状态的消息模板
        if current_state == "绿灯":
            return (
                f"当前Token用量为{used}，硬限制为{hard}，"
                f"当前使用{taken*100:.1f}%（绿灯状态）。"
                f"当前已有{message_count}条消息。"
                "可以顺手标记大消息，无需担心token限制。"
            )

        if current_state == "绿灯闪烁":
            return (
                f"当前Token用量为{used}，硬限制为{hard}，"
                f"当前使用{taken*100:.1f}%（绿灯闪烁状态）。"
                f"当前已有{message_count}条消息。"
                "应该积极标记大消息，可以顺手删除一些实在和当前任务无关的消息。"
            )

        if current_state == "黄灯":
            return (
                f"当前Token用量为{used}，硬限制为{hard}，"
                f"当前使用{taken*100:.1f}%（黄灯状态）。"
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
        action_guide = (
            "当前有至少5条垃圾消息，建议调用message_garbage_clean清理垃圾消息。"
        )
        if garbage_count < 5:
            action_guide = "建议调用compress_history_range删除大约一半消息！"

        return (
            f"当前Token用量为{used}，硬限制为{hard}，"
            f"当前使用{taken*100:.1f}%（红灯状态）。"
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
            name="message_garbage_clean",
            desc="清理已经标记的垃圾消息",
            args={},
            required_args=[],
        )
        async def message_garbage_clean_tool() -> str:
            result = await self.message_garbage_clean()
            self.last_compress_or_clean_time = time.time()
            return result

        @toolset.register_tool(
            name="thanox_history",
            desc="随机删除一半消息（不包括前5条系统消息）。",
            args={},
            required_args=[],
        )
        async def thanox_history() -> str:
            self.last_compress_or_clean_time = time.time()
            return await self.thanox_history()

        return toolset

    def get_workflow_toolset(self) -> "ToolSet":
        """获取工作流工具集。

        Returns:
            包含工作流工具的ToolSet
        """
        from linhai.tool.base import ToolSet

        toolset = ToolSet()

        @toolset.register_tool(
            name="compress_history_range",
            desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            args={},
            required_args=[],
        )
        async def compress_history_range_tool() -> str:
            from linhai.agent import Agent

            agent = self.group_chat.get_members("agent", Agent)
            result = await compress_history_range(agent)
            self.last_compress_or_clean_time = time.time()
            return result

        return toolset

    def _register_lifecycle_callbacks(self) -> None:
        """注册生命周期回调。"""
        from .lifecycle import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_after_working(self._on_after_working)
        lifecycle.register_after_tool_call(self._on_after_tool_call)

    async def _on_after_tool_call(
        self,
        _agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        _success: bool,
    ) -> Optional[RuntimeMessage]:
        tool_result_content = str(tool_result)
        if len(tool_result_content) > 3000:
            message_id = self.record_large_message(tool_result, tool_result_content)
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

    async def _on_after_working(self, _agent) -> None:
        """工作完成后的回调，重置压缩工具调用状态。

        Args:
            agent: Agent实例
        """
        self.compress_tool_called_in_last_response = False
