"""
消息编排模块，负责管理大消息、垃圾消息、阈值通知等高级消息管理功能。
"""

from __future__ import annotations
import tiktoken
import random
from pathlib import Path
import time
import reprlib
from typing import Optional, Literal, TypedDict, TYPE_CHECKING, Union

from linhai.agent.workflow import (
    context_compress_range_step1,
    context_compress_range_step2,
)
from .lifecycle import Lifecycle
from linhai.llm import ToolCallMessage, Answer
from linhai.tool.base import ToolCallResultMessage
from linhai.multimodal import ImageMessage
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolResultSuccess, ToolResultFailed, ToolArgInfo
from linhai.utils import CliRuntimeNotice
from linhai.type_hints import ThresholdInfo
from linhai.token_manager import TokenManager
from .base import Message, RuntimeMessage
from .message import AgentMessage
from .conversation import save_cleaned_messages

if TYPE_CHECKING:
    from .main import Agent

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
        self.last_compress_or_clean_time: Optional[float] = None

        self._register_lifecycle_callbacks()

    async def context_garbage_clean(self) -> ToolResultSuccess | ToolResultFailed:
        """清理所有大消息。

        Returns:
            清理结果消息。如果当前大消息少于5条则返回失败消息。
        """
        large_count = len(self.large_messages)
        if large_count < 5:
            return ToolResultFailed(
                content=f"需要至少5条大消息，当前只有{large_count}条"
            )

        removed_messages = list(self.large_messages)
        for message in removed_messages:
            await self.agent_message.remove_message(message)
        self.large_messages.clear()
        self.last_compress_or_clean_time = time.time()

        conversation_dir = self.group_chat.get_members("conversation_folder", Path)
        saved_path = save_cleaned_messages(
            conversation_dir, removed_messages, prefix="garbage_clean"
        )
        result = f"清理了{large_count}条大消息，保存到: {saved_path}"
        return ToolResultSuccess(content=result)

    def compute_orchestration_context(
        self, tool_name: str, threshold_info: Optional[ThresholdInfo]
    ) -> dict:
        """计算编排上下文信息，合并多个函数的功能。

        Args:
            tool_name: 工具名称
            threshold_info: 阈值信息，可能为None

        Returns:
            包含以下键的字典：
                threshold_info: 传入的阈值信息
                current_state: 红绿灯状态字符串
                recently_called_cleanup: 布尔值，一分钟内是否调用过清理工具
                notification_message: 提示消息字符串，可能为None
                tool_block_details: ToolBlockDetailsDict
        """
        if threshold_info is None:
            return {
                "threshold_info": None,
                "current_state": "绿灯",
                "recently_called_cleanup": False,
                "notification_message": None,
                "tool_block_details": {
                    "blocked_category": None,
                    "actual_category": "other",
                    "recently_called_cleanup": False,
                    "current_state": "绿灯",
                },
            }

        usage_ratio = threshold_info["usage_ratio"]
        percentage = usage_ratio * 100
        if percentage < 70:
            current_state = "绿灯"
        elif 70 <= percentage < 90:
            current_state = "黄灯"
        else:
            current_state = "红灯"

        recently_called_cleanup = False
        if self.last_compress_or_clean_time:
            time_since_last_cleanup = time.time() - self.last_compress_or_clean_time
            recently_called_cleanup = time_since_last_cleanup < 60

        actual_category = (
            "cleanup"
            if tool_name
            in {
                "context_compress_range_step1",
                "context_compress_range_step2",
                "context_garbage_clean",
            }
            else "other"
        )
        if tool_name == "context_compress_range_step2":
            blocked_category = None
        elif current_state == "红灯":
            if recently_called_cleanup:
                blocked_category = "cleanup"
            else:
                blocked_category = "other"
        elif current_state == "黄灯":
            if recently_called_cleanup:
                blocked_category = "cleanup"
            else:
                blocked_category = None
        else:
            blocked_category = None

        tool_block_details: ToolBlockDetailsDict = {
            "blocked_category": blocked_category,
            "actual_category": actual_category,
            "recently_called_cleanup": recently_called_cleanup,
            "current_state": current_state,
        }

        notification_message = None
        if current_state != "绿灯" or recently_called_cleanup:
            large_count = len(self.large_messages)
            recently_called_text = "有" if recently_called_cleanup else "没有"
            cache_ratio_text = ""
            token_manager = self.group_chat.get_members("token_manager", TokenManager)
            if token_manager.cumulative_token_usage is not None:
                input_tokens = token_manager.cumulative_token_usage.get(
                    "input_tokens", 0
                )
                cached_input_tokens = token_manager.cumulative_token_usage.get(
                    "cached_input_tokens", 0
                )
                if input_tokens > 0:
                    cache_ratio = (cached_input_tokens / input_tokens) * 100
                    cache_ratio_text = f", 缓存比例: {cache_ratio:.0f}%"
            base_info = f"当前为{current_state}状态, 上下文占用量为{percentage:.1f}%, 当前有{large_count}条大消息, 一分钟内{recently_called_text}调用过消息清理工具{cache_ratio_text}"
            if recently_called_cleanup:
                suggestion = "建议: 继续，在上下文实际长度更新之后runtime会另行通知"
            elif current_state == "红灯":
                suggestion = "建议: 立即暂停当前任务"
            elif current_state == "黄灯":
                suggestion = (
                    "建议: 应该调用context_garbage_clean工具"
                    if large_count >= 5
                    else "建议: 应该避免读取文件，直接开始修改文件"
                )
            else:
                suggestion = "建议: 不要担心消息限制，立即工作"
            notification_message = f"{base_info}, {suggestion}"

        return {
            "threshold_info": threshold_info,
            "current_state": current_state,
            "recently_called_cleanup": recently_called_cleanup,
            "notification_message": notification_message,
            "tool_block_details": tool_block_details,
        }

    def get_status_display_pieces(self, use_nerd_font: bool = False) -> list[str]:
        """获取状态显示片段列表，用于CLI底栏。

        Args:
            use_nerd_font: 是否使用nerd font符号

        Returns:
            状态显示片段列表，每个片段是一个独立的显示单元
        """
        message_count = len(self.agent_message.get_messages())
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

    def get_orchestration_toolset(self) -> "ToolSet":
        """获取编排工具集，合并消息管理和工作流工具。

        Returns:
            包含编排工具的ToolSet
        """

        toolset = ToolSet()

        @toolset.register_tool(
            name="context_garbage_clean",
            desc="清理大消息：如果当前有至少5条大消息，全部删除并返回每条被删除的消息的repr。",
            args={},
            required_args=[],
        )
        async def context_garbage_clean_tool() -> ToolResultSuccess | ToolResultFailed:
            self.last_compress_or_clean_time = time.time()
            return await self.context_garbage_clean()

        @toolset.register_tool(
            name="context_compress_range_step1",
            desc="压缩范围第一步：生成消息列表总结并返回range_clean_id。",
            args={},
            required_args=[],
        )
        async def context_compress_range_step1_tool() -> (
            ToolResultSuccess | ToolResultFailed
        ):
            result = await context_compress_range_step1(self.group_chat)
            self.last_compress_or_clean_time = time.time()
            return result

        @toolset.register_tool(
            name="context_compress_range_step2",
            desc="压缩范围第二步：使用range_clean_id确认删除范围并执行删除。",
            args={
                "range_clean_id": ToolArgInfo(
                    desc="range_clean_id，从第一步获取",
                    type="str",
                ),
                "start_id": ToolArgInfo(
                    desc="开始删除的消息ID",
                    type="int",
                ),
                "end_id": ToolArgInfo(
                    desc="结束删除的消息ID",
                    type="int",
                ),
                "description": ToolArgInfo(
                    desc="描述删除内容，建议包含待办任务",
                    type="str",
                ),
            },
            required_args=["range_clean_id", "start_id", "end_id", "description"],
        )
        async def context_compress_range_step2_tool(
            range_clean_id: str, start_id: int, end_id: int, description: str
        ) -> ToolResultSuccess | ToolResultFailed:
            result = await context_compress_range_step2(
                self.group_chat, range_clean_id, start_id, end_id, description
            )
            self.last_compress_or_clean_time = time.time()
            return result

        return toolset

    def _register_lifecycle_callbacks(self) -> None:
        """注册生命周期回调。"""
        from .lifecycle import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)
        lifecycle.register_on_tool_result(self._on_tool_result)
        lifecycle.register_before_message_generation(self._before_message_generation)

        large_message_plugin = LargeMessageCountPlugin(self.group_chat)
        large_message_plugin.register(lifecycle)

    async def _on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        if isinstance(message, ImageMessage):
            self.large_messages.add(message)
        elif status == "success" and message is not None:
            tokenizer = tiktoken.get_encoding("cl100k_base")
            content = str(message.to_llm_message().get("content", ""))
            token_count = len(tokenizer.encode(content))
            if token_count > 800:
                self.large_messages.add(message)
        return None

    async def _before_message_generation(
        self, enable_compress: bool, disable_waiting_user_warning: bool
    ) -> None:
        """在消息生成前清理无效的大消息引用。"""
        valid_messages = set(self.agent_message.messages)
        self.large_messages = {
            msg for msg in self.large_messages if msg in valid_messages
        }


class RedStateToolBlockPlugin:
    """红灯状态工具调用拦截插件。

    在红灯状态且一分钟内没有调用过消息清理类工具时禁止调用其他工具。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.CLEANUP_TOOLS = {
            "context_compress_range_step1",
            "context_compress_range_step2",
            "context_garbage_clean",
        }

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict | None,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, "RuntimeMessage"]:
        """检查是否需要跳过工具调用。

        Returns:
            None: 没有特殊处理
            bool: 仅当status为"skipped"时有效，True表示跳过工具调用
            RuntimeMessage: 替换工具结果
        """
        if status != "skipped":
            return None

        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        threshold_info = agent.get_threshold_info()
        if threshold_info is None:
            return None

        if orchestration is None:
            return None

        context = orchestration.compute_orchestration_context(tool_name, threshold_info)
        details = context["tool_block_details"]

        if details["blocked_category"] == details["actual_category"]:
            recently_called_cleanup = details["recently_called_cleanup"]
            current_state = details["current_state"]

            if details["blocked_category"] == "cleanup" and recently_called_cleanup:
                error_msg = f"一分钟内已经调用过消息清理工具，禁止调用{tool_name}工具"
                ui_msg = f"一分钟内已调用过消息清理工具，禁止调用{tool_name}工具"
            else:
                error_msg = (
                    f"错误：当前处于{current_state}状态（token使用率{threshold_info['usage_ratio']*100:.1f}%），"
                    f"禁止调用{tool_name}工具！"
                    "红灯状态下只允许调用消息管理工具。"
                )
                ui_msg = f"{current_state}状态下阻止调用{tool_name}工具，请先调用消息清理类工具"

            await agent.interrupt(error_msg, ui_msg)
            return True

        return None

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_on_tool_result(self.on_tool_result)


class NotificationMessagePlugin:
    """添加notification message的插件。

    将添加notification message的实现拆分成一个新的plugin类。
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def before_message_generation(
        self,
        _enable_compress: bool,
        _disable_waiting_user_warning: bool,
    ) -> None:
        """在消息生成前添加notification message。"""
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

        context = orchestration.compute_orchestration_context("", threshold_info)
        notification_message = context["notification_message"]
        if notification_message is not None:
            agent.message_processor.update_notification_message(
                RuntimeMessage(notification_message),
                source="threshold_notification",
                sort_value=0,
            )

    async def after_message_generation(
        self,
        _answer: Answer,
        _full_response: str,
        _tool_calls: list[dict],
    ) -> None:
        """在消息生成后添加notification message。"""
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

        context = orchestration.compute_orchestration_context("", threshold_info)
        notification_message = context["notification_message"]
        if notification_message is not None:
            agent.message_processor.update_notification_message(
                RuntimeMessage(notification_message),
                source="threshold_notification",
                sort_value=0,
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
        lifecycle.register_after_message_generation(self.after_message_generation)


class LargeMessageCountPlugin:
    """大消息数量通知插件。

    根据大消息数量动态管理notification_message：
    - 大消息少于5条时：提示不能调用context_garbage_clean
    - 大消息至少5条时：删除提示（不添加notification_message）
    """

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    async def before_message_generation(
        self,
        _enable_compress: bool,
        _disable_waiting_user_warning: bool,
    ) -> None:
        """在消息生成前根据大消息数量管理notification_message。"""
        from .main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        orchestration = self.group_chat.get_members(
            "agent_context_orchestration", AgentContextOrchestration
        )

        if orchestration is None:
            return

        large_count = len(orchestration.large_messages)

        if large_count < 5:

            message_content = f"当前只有{large_count}条大消息，需要至少5条大消息才能调用context_garbage_clean"
            agent.message_processor.update_notification_message(
                RuntimeMessage(message_content),
                source="large_message_count",
                sort_value=0,
            )
        else:

            agent.message_processor.update_notification_message(
                None, source="large_message_count", sort_value=0
            )

    def register(self, lifecycle: "Lifecycle"):
        """注册插件回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)
