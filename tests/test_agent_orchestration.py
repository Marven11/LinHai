"""AgentContextOrchestration类的单元测试。"""

import unittest
import time
from unittest.mock import Mock, AsyncMock, patch

from linhai.agent.orchestration import (
    AgentContextOrchestration,
    ThresholdInfo,
    get_cleanable_large_messages,
)
from linhai.agent.message import AgentMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.agent.lifecycle import Lifecycle
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager


class TestAgentContextOrchestration(unittest.IsolatedAsyncioTestCase):
    """AgentContextOrchestration类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        # 注册一个mock的lifecycle以避免RuntimeError
        mock_lifecycle = AsyncMock(spec=Lifecycle)
        mock_lifecycle.trigger_before_add_new_message.return_value = None
        self.group_chat.register_member("lifecycle", mock_lifecycle)

        # 注册一个mock的tool_manager，因为SystemMessage初始化需要它
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.group_chat.register_member("tool_manager", mock_tool_manager)

        # 注册一个mock的token_manager，因为compute_orchestration_context需要它
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.get_large_message_reprs = Mock(return_value=[])
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.is_dirty = False
        self.group_chat.register_member("token_manager", mock_token_manager)

        # 注册一个mock的llm_manager，因为is_explicit_cache_enabled需要它
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_explicit_cache_info = Mock(return_value=None)
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.group_chat.register_member("llm_manager", mock_llm_manager)

        # 注册conversation_folder，因为AgentMessage._save_context需要它
        from pathlib import Path
        from tempfile import TemporaryDirectory

        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.group_chat.register_member("conversation_folder", Path(self.temp_dir.name))

        self.init_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(self.group_chat, self.init_messages)
        self.orchestration = AgentContextOrchestration(
            self.group_chat, self.message_processor
        )

    async def test_add_soft_threshold_notification(self):
        """测试添加软限制通知。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 60000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.8,
        }
        # 添加一个大消息，以便在黄灯状态下可以显示大消息信息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        await self.message_processor.add_new_message(large_msg)

        # 调用compute_orchestration_context，获取通知消息
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        result = context["notification_message"]

        # 验证返回值
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("黄灯状态", result)
        self.assertIn("上下文占用量", result)
        self.assertIn("条大消息", result)
        # 消息数量应该仍然是3（2条pinned_messages + 1条普通消息），因为通知没有被添加，只是返回
        self.assertEqual(len(self.message_processor.get_messages()), 3)

    async def test_add_soft_threshold_notification_with_dirty_state(self):
        """测试token用量失效状态下添加通知。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 60000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.6,
        }
        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        await self.message_processor.add_new_message(large_msg)

        # 设置token用量失效
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        # 调用compute_orchestration_context，获取通知消息
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        result = context["notification_message"]

        # 对于失效状态，应该返回消息字符串
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("失效状态", result)
        self.assertIn("token用量信息已失效", result)
        # 消息数量应该仍然是3（2条pinned_messages + 1条普通消息）
        self.assertEqual(len(self.message_processor.get_messages()), 3)

    async def test_get_status_display_piece(self):
        """测试获取状态显示片段。"""
        await self.message_processor.add_new_message(RuntimeMessage("test"))

        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        await self.message_processor.add_new_message(large_msg)

        # 不再需要标记垃圾，因为功能已删除

        # 测试不使用nerd font
        pieces = self.orchestration.get_status_display_pieces(use_nerd_font=False)
        self.assertIsInstance(pieces, list)
        self.assertGreater(len(pieces), 0)
        # 应该包含消息计数 - 格式已改为 '4 msgs', '1 large'
        for piece in pieces:
            if "msgs" in piece:
                self.assertIn(
                    "4", piece
                )  # 总消息数量: 2条pinned_messages + 2条普通消息
            elif "large" in piece:
                self.assertIn("1", piece)  # 大消息数量

        # 测试使用nerd font
        nerd_pieces = self.orchestration.get_status_display_pieces(use_nerd_font=True)
        self.assertIsInstance(nerd_pieces, list)
        self.assertGreater(len(nerd_pieces), 0)
        # nerd字体使用图标，所以我们检查是否包含消息数量
        for piece in nerd_pieces:
            if "\uf27a" in piece:  # 消息图标
                self.assertIn(
                    "4", piece
                )  # 总消息数量: 2条pinned_messages + 2条普通消息
            elif "\uf1c0" in piece:  # 大消息图标
                self.assertIn("1", piece)

    def test_determine_tool_category(self):
        """测试工具分类判断。"""
        # 创建一个阈值信息，状态为绿灯，以便测试工具分类
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5,
        }

        # 测试消息清理工具
        context = self.orchestration.compute_orchestration_context(
            "context_forget_range_step1", threshold_info
        )
        self.assertEqual(context["tool_block_details"]["actual_category"], "cleanup")

        context = self.orchestration.compute_orchestration_context(
            "context_forget_large_message", threshold_info
        )
        self.assertEqual(context["tool_block_details"]["actual_category"], "cleanup")

        # 测试其他工具
        context = self.orchestration.compute_orchestration_context(
            "read_file", threshold_info
        )
        self.assertEqual(context["tool_block_details"]["actual_category"], "other")

    def test_determine_threshold_state(self):
        """测试阈值状态判断。"""
        # 通过compute_orchestration_context测试状态判断
        threshold_info = {
            "hard_limit": 100000,
            "used_tokens": 30000,
            "remaining_tokens": 70000,
            "usage_ratio": 0.3,
        }
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        self.assertEqual(context["current_state"], "绿灯")

        threshold_info = {
            "hard_limit": 100000,
            "used_tokens": 55000,
            "remaining_tokens": 45000,
            "usage_ratio": 0.55,
        }
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        self.assertEqual(context["current_state"], "绿灯")

        threshold_info = {
            "hard_limit": 100000,
            "used_tokens": 75000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.75,
        }
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        self.assertEqual(context["current_state"], "黄灯")

        threshold_info = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        self.assertEqual(context["current_state"], "红灯")

    async def test_token_manager_is_dirty_state(self):
        """测试token管理器的is_dirty状态。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 60000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.6,
        }
        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        await self.message_processor.add_new_message(large_msg)

        # 获取token管理器并设置dirty状态
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        context = self.orchestration.compute_orchestration_context("", threshold_info)
        # 检查通知消息中包含失效状态
        self.assertIsNotNone(context["notification_message"])
        assert context["notification_message"] is not None
        self.assertIn("失效状态", context["notification_message"])

    def test_red_state_with_dirty_state_allows_normal_tools(self):
        """测试红灯状态下，如果token用量失效，正常工具应该被允许。"""

        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 设置token用量失效
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        # 测试正常工具（如read_file）不应该被阻塞
        context = self.orchestration.compute_orchestration_context(
            "read_file", threshold_info
        )
        details = context["tool_block_details"]

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：工具类别是other
        self.assertEqual(details["actual_category"], "other")
        # 验证：阻塞的类别应该是cleanup（阻塞清理工具，允许其他工具）
        self.assertEqual(details["blocked_category"], "cleanup")
        # 验证：因为blocked_category是cleanup，而actual_category是other，所以不应该被拦截
        self.assertNotEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_without_dirty_state_blocks_normal_tools(self):
        """测试红灯状态下，如果token用量未失效，正常工具应该被阻塞。"""

        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 确保token用量未失效（默认状态）
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = False

        # 测试正常工具（如read_file）应该被阻塞
        context = self.orchestration.compute_orchestration_context(
            "read_file", threshold_info
        )
        details = context["tool_block_details"]

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：工具类别是other
        self.assertEqual(details["actual_category"], "other")
        # 验证：阻塞的类别应该是other（阻塞正常工具）
        self.assertEqual(details["blocked_category"], "other")
        # 验证：因为blocked_category和actual_category都是other，所以应该被拦截
        self.assertEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_without_dirty_state_allows_cleanup_tools(self):
        """测试红灯状态下，如果token用量未失效，清理工具应该被允许。"""
        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 确保token用量未失效（默认状态）
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = False

        # 测试清理工具（如context_forget_large_message）应该被允许
        context = self.orchestration.compute_orchestration_context(
            "context_forget_large_message", threshold_info
        )
        details = context["tool_block_details"]

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：工具类别是cleanup
        self.assertEqual(details["actual_category"], "cleanup")
        # 验证：阻塞的类别应该是other（阻塞正常工具，允许清理工具）
        self.assertEqual(details["blocked_category"], "other")
        # 验证：因为blocked_category是other，而actual_category是cleanup，所以不应该被拦截
        self.assertNotEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_tool_block_logic(self):
        """测试红灯状态下的工具拦截逻辑。"""
        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 测试token用量失效时，清理工具被阻塞（因为刚清理过）
        token_manager = self.group_chat.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        context = self.orchestration.compute_orchestration_context(
            "context_forget_large_message", threshold_info
        )
        details = context["tool_block_details"]
        self.assertEqual(details["blocked_category"], "cleanup")
        self.assertEqual(details["actual_category"], "cleanup")

        # 测试token用量未失效时，正常工具被阻塞（允许清理工具）
        token_manager.is_dirty = False
        context = self.orchestration.compute_orchestration_context(
            "read_file", threshold_info
        )
        details = context["tool_block_details"]
        self.assertEqual(details["blocked_category"], "other")
        self.assertEqual(details["actual_category"], "other")

    def test_yellow_state_allows_cleanup_tools(self):
        """测试黄灯状态下，清理工具应该被允许。"""

        # 设置黄灯状态（使用率75%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 75000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.75,
        }

        # 测试清理工具（如context_forget_large_message）应该不被阻塞
        context = self.orchestration.compute_orchestration_context(
            "context_forget_large_message", threshold_info
        )
        details = context["tool_block_details"]

        # 验证：当前状态应该是黄灯
        self.assertEqual(details["current_state"], "黄灯")
        # 验证：工具类别是cleanup
        self.assertEqual(details["actual_category"], "cleanup")
        # 验证：阻塞的类别应该是None（黄灯下不阻塞清理工具）
        self.assertEqual(details["blocked_category"], None)
        # 验证：因为blocked_category是None，所以不应该被拦截
        self.assertNotEqual(details["blocked_category"], details["actual_category"])

    def test_get_cleanable_large_messages(self):
        """测试get_cleanable_large_messages函数。"""
        from linhai.agent.base import Message

        # 添加100条普通消息
        for i in range(100):
            msg = RuntimeMessage(f"message {i}")
            self.message_processor.messages.append(msg)

        # 在第25, 50, 75, 100位置添加4个大消息（索引为24, 49, 74, 99）
        large_msgs = []
        for pos in [24, 49, 74, 99]:
            large_msg = RuntimeMessage(f"Large content at position {pos}" + "x" * 1000)
            large_msgs.append(large_msg)
            self.message_processor.messages[pos] = large_msg
            self.orchestration.large_messages.add(large_msg)

        # 测试：最近20条内的大消息应该被保留
        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            recent_count=20
        )

        # 100个消息，最近20条是80-99，所以索引99的大消息应该被保留
        # 索引24, 49, 74的大消息应该可以被清理
        self.assertEqual(len(cleanable), 3)
        self.assertIn(large_msgs[0], cleanable)  # 索引24
        self.assertIn(large_msgs[1], cleanable)  # 索引49
        self.assertIn(large_msgs[2], cleanable)  # 索引74
        self.assertNotIn(large_msgs[3], cleanable)  # 索引99，应该被保留

    def test_get_cleanable_large_messages_two_recent(self):
        """测试当有2个大消息在recent_count内时的行为。"""
        # 添加100条普通消息
        for i in range(100):
            msg = RuntimeMessage(f"message {i}")
            self.message_processor.messages.append(msg)

        # 在第25, 50, 90, 100位置添加4个大消息
        large_msgs = []
        for pos in [24, 49, 89, 99]:  # 90和100在recent_count=20内
            large_msg = RuntimeMessage(f"Large content at position {pos}" + "x" * 1000)
            large_msgs.append(large_msg)
            self.message_processor.messages[pos] = large_msg
            self.orchestration.large_messages.add(large_msg)

        # 测试：90和100位置的大消息应该被保留
        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            recent_count=20
        )

        # 只有索引24, 49的大消息可以被清理
        # 索引89, 99的大消息应该被保留
        self.assertEqual(len(cleanable), 2)
        self.assertIn(large_msgs[0], cleanable)  # 索引24
        self.assertIn(large_msgs[1], cleanable)  # 索引49
        self.assertNotIn(large_msgs[2], cleanable)  # 索引89，应该被保留
        self.assertNotIn(large_msgs[3], cleanable)  # 索引99，应该被保留
