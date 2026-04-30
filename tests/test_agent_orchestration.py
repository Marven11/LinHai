"""AgentContextOrchestration类的单元测试。"""

import unittest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from linhai.agent.orchestration import (
    AgentContextOrchestration,
    ThresholdInfo,
    get_cleanable_large_messages,
)
from linhai.agent.message import AgentMessage
from linhai.base import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.messages import RuntimeMessage
from linhai.registry import Registry
from linhai.agent.lifecycle import Lifecycle
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager


class TestAgentContextOrchestration(unittest.IsolatedAsyncioTestCase):
    """AgentContextOrchestration类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        Lifecycle(self.registry)

        # 注册一个mock的tool_manager，因为SystemMessage初始化需要它
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.registry.register_member("tool_manager", mock_tool_manager)

        # 注册一个mock的token_manager，因为compute_orchestration_context需要它
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.get_large_message_reprs = Mock(return_value=[])
        mock_token_manager.cumulative_token_usage = None
        mock_token_manager.is_dirty = False
        self.registry.register_member("token_manager", mock_token_manager)

        # 注册一个mock的llm_manager，因为is_explicit_cache_enabled需要它
        from linhai.llm_manager import LlmManager

        mock_llm_manager = Mock(spec=LlmManager)
        mock_llm = Mock()
        mock_llm.get_explicit_cache_info = Mock(return_value=None)
        mock_llm_manager.get_current_llm = Mock(return_value=mock_llm)
        self.registry.register_member("llm_manager", mock_llm_manager)

        # 注册conversation_folder，因为AgentMessage._save_context需要它
        from pathlib import Path
        from tempfile import TemporaryDirectory

        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.registry.register_member("conversation_folder", Path(self.temp_dir.name))

        self.init_messages = [
            SystemMessage(
                registry=self.registry,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(self.registry, self.init_messages)
        self.orchestration = AgentContextOrchestration(
            self.registry, self.message_processor
        )

        # 注册一个mock的agent，因为NotificationMessagePlugin需要它
        from linhai.agent.main import Agent

        mock_agent = Mock(spec=Agent)
        mock_agent.message_processor = self.message_processor
        mock_agent.get_threshold_info = Mock(return_value=None)
        self.registry.register_member("agent", mock_agent)

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
        self.assertIn("黄灯", result)
        self.assertIn("%", result)
        self.assertIn(": 1", result)
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
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        # 调用compute_orchestration_context，获取通知消息
        context = self.orchestration.compute_orchestration_context("", threshold_info)
        result = context["notification_message"]

        # 对于失效状态，应该返回消息字符串
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn(": 1", result)
        self.assertIn("token", result)
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
        # 更新agent的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

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
            "used_tokens": 85000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.85,
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
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.is_dirty = True

        context = self.orchestration.compute_orchestration_context("", threshold_info)
        # 检查通知消息中包含失效状态
        self.assertIsNotNone(context["notification_message"])
        assert context["notification_message"] is not None
        self.assertIn("token", context["notification_message"])

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
        token_manager = self.registry.get_member_typechecked(
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
        token_manager = self.registry.get_member_typechecked(
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
        token_manager = self.registry.get_member_typechecked(
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
        token_manager = self.registry.get_member_typechecked(
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

        # 设置黄灯状态（使用率85%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 85000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.85,
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
        from linhai.base import Message

        # 添加100条普通消息
        for i in range(100):
            msg = RuntimeMessage(f"message {i}")
            self.message_processor.messages.append(msg)

        # 在第25, 50, 85, 100位置添加4个大消息（索引为24, 49, 74, 99）
        large_msgs = []
        for pos in [24, 49, 74, 99]:
            large_msg = RuntimeMessage(f"Large content at position {pos}" + "x" * 1000)
            large_msgs.append(large_msg)
            self.message_processor.messages[pos] = large_msg
            self.orchestration.large_messages.add(large_msg)

        # 测试：所有大消息都是可清理的（因为没有在cleaned_messages_dict中）
        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )

        # 所有4个大消息都是可清理的（因为没有在cleaned_messages_dict中）
        self.assertEqual(len(cleanable), 4)
        for msg in large_msgs:
            self.assertIn(msg, cleanable)

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

        # 测试：所有大消息都是可清理的（因为没有在cleaned_messages_dict中）
        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )

        # 所有4个大消息都是可清理的（因为没有在cleaned_messages_dict中）
        self.assertEqual(len(cleanable), 4)
        for msg in large_msgs:
            self.assertIn(msg, cleanable)

    def test_cleaned_messages_dict_expiry(self):
        """测试cleaned_messages字典的过期清理机制。"""
        current_time = time.time()

        test_hashes = {
            "hash1": current_time - 200,
            "hash2": current_time - 100,
            "hash3": current_time - 50,
        }
        self.orchestration.cleaned_messages = test_hashes.copy()

        get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )

        self.assertNotIn("hash1", self.orchestration.cleaned_messages)
        self.assertIn("hash2", self.orchestration.cleaned_messages)
        self.assertIn("hash3", self.orchestration.cleaned_messages)
        self.assertEqual(len(self.orchestration.cleaned_messages), 2)

    def test_get_cleanable_large_messages_duplicate_content(self):
        """测试get_cleanable_large_messages对重复内容的检查。"""
        test_content = "This is a test message that will be hashed"
        msg = RuntimeMessage(test_content)

        self.message_processor.messages.append(msg)
        self.orchestration.large_messages.add(msg)

        import hashlib

        # 使用消息的实际内容计算哈希
        actual_content = msg.get_content()
        content_hash = hashlib.md5(actual_content.encode()).hexdigest()
        self.orchestration.cleaned_messages[content_hash] = time.time() - 100

        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )
        self.assertNotIn(msg, cleanable)

        self.orchestration.cleaned_messages[content_hash] = time.time() - 200
        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )
        self.assertNotIn(content_hash, self.orchestration.cleaned_messages)

        binary_msg = RuntimeMessage(b"binary content")
        self.message_processor.messages.append(binary_msg)
        self.orchestration.large_messages.add(binary_msg)

        cleanable = get_cleanable_large_messages(
            self.orchestration.large_messages,
            self.message_processor,
            cleaned_messages_dict=self.orchestration.cleaned_messages,
        )
        self.assertIn(binary_msg, cleanable)

    def test_toolset_conflict_with_parameter(self):
        """测试工具集的conflict_with参数。"""
        toolset = self.orchestration.get_context_cleaning_toolset()
        tools = toolset.get_tools()

        # 检查context_forget_large_message
        large_message_tool = tools.get("context_forget_large_message")
        self.assertIsNotNone(large_message_tool)
        self.assertIn("conflict_with", large_message_tool)
        self.assertEqual(
            set(large_message_tool["conflict_with"]),
            {"context_forget_range_step1", "context_forget_range_step2"},
        )

        # 检查context_forget_range_step1
        step1_tool = tools.get("context_forget_range_step1")
        self.assertIsNotNone(step1_tool)
        self.assertIn("conflict_with", step1_tool)
        self.assertEqual(
            set(step1_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step2"},
        )

        # 检查context_forget_range_step2
        step2_tool = tools.get("context_forget_range_step2")
        self.assertIsNotNone(step2_tool)
        self.assertIn("conflict_with", step2_tool)
        self.assertEqual(
            set(step2_tool["conflict_with"]),
            {"context_forget_large_message", "context_forget_range_step1"},
        )

    async def test_consecutive_red_block_notification_not_shows_after_two_blocks(
        self,
    ):
        """测试两次红灯拦截后不显示通知消息。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 模拟两次红灯拦截
        self.orchestration.consecutive_red_block_count = 2

        # 调用before_message_generation
        from linhai.agent.orchestration import NotificationMessagePlugin

        plugin = NotificationMessagePlugin(self.registry)
        await plugin.before_message_generation()

        # 验证notification message不存在（因为count<3）
        notifications = self.message_processor.notification_messages.get(
            "consecutive_red_block"
        )
        self.assertIsNone(notifications)

    async def test_consecutive_red_block_notification_shows_after_three_blocks(
        self,
    ):
        """测试三次红灯拦截后显示通知消息。"""
        # 修改mock_agent返回红灯状态的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟三次红灯拦截
        self.orchestration.consecutive_red_block_count = 3

        # 调用before_message_generation
        from linhai.agent.orchestration import NotificationMessagePlugin

        plugin = NotificationMessagePlugin(self.registry)
        await plugin.before_message_generation()

        # 验证notification message存在
        notifications = self.message_processor.notification_messages.get(
            "consecutive_red_block"
        )
        self.assertIsNotNone(notifications)
        # 验证消息内容符合issue要求
        notification_msg = notifications["message"].get_content()
        self.assertIn("json toolcall", notification_msg)
        self.assertIn("```json toolcall", notification_msg)

    async def test_consecutive_red_block_notification_cleared_after_success(
        self,
    ):
        """测试工具调用成功后清除通知消息。"""
        # 修改mock_agent返回红灯状态的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟三次红灯拦截
        self.orchestration.consecutive_red_block_count = 3

        # 添加通知消息
        from linhai.agent.orchestration import NotificationMessagePlugin

        plugin = NotificationMessagePlugin(self.registry)
        await plugin.before_message_generation()

        # 验证notification message存在
        notifications = self.message_processor.notification_messages.get(
            "consecutive_red_block"
        )
        self.assertIsNotNone(notifications)

        # 模拟工具调用成功 - 使用绿灯状态，工具不被阻止时才会重置计数器
        # 首先清除红灯状态
        self.orchestration.consecutive_red_block_count = 0
        mock_agent.get_threshold_info = Mock(
            return_value={
                "hard_limit": 100000,
                "used_tokens": 30000,
                "remaining_tokens": 70000,
                "usage_ratio": 0.3,  # 绿灯状态
            }
        )

        from linhai.agent.orchestration import RedStateToolBlockPlugin

        block_plugin = RedStateToolBlockPlugin(self.registry)
        await block_plugin.before_toolcall(
            tool_name="read_file",
            toolcall_arguments={},
            with_secret=None,
        )

        # 验证计数器被重置（绿灯状态下工具不被阻止）
        self.assertEqual(self.orchestration.consecutive_red_block_count, 0)

        # 验证notification message被清除
        notifications = self.message_processor.notification_messages.get(
            "consecutive_red_block"
        )
        self.assertIsNone(notifications)

    async def test_compute_orchestration_context_returns_cache_ratio(self):
        """测试compute_orchestration_context返回cache_ratio字段。"""
        # 设置token manager的cumulative_token_usage以计算缓存比例
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.cumulative_token_usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 600,  # 缓存比例应为60%
            "output_tokens": 0,
        }
        # 确保input_tokens > 0 以计算cache_ratio

        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5,
        }

        context = self.orchestration.compute_orchestration_context("", threshold_info)
        self.assertIn("cache_ratio", context)
        self.assertAlmostEqual(context["cache_ratio"], 60.0, places=1)

    async def test_cache_ratio_reminder_green_state_low_cache(self):
        """测试绿灯状态且缓存命中率低于90%时发送提醒。"""
        # 设置绿灯状态（使用率50%）和低缓存比例（60%）
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.cumulative_token_usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 600,
            "output_tokens": 0,
        }

        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5,
        }

        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟清理工具调用
        from linhai.agent.orchestration import RedStateToolBlockPlugin

        plugin = RedStateToolBlockPlugin(self.registry)

        # 捕获UI日志
        ui_log_calls = []

        async def mock_send_ui_log(event_name, ui_notice):
            ui_log_calls.append(ui_notice)

        self.registry.send_if_exists = AsyncMock(side_effect=mock_send_ui_log)

        # 调用before_toolcall，应该发送提醒但不阻止工具
        result = await plugin.before_toolcall(
            tool_name="context_forget_large_message",
            toolcall_arguments={},
            with_secret=None,
        )

        # 验证：不应返回FailedToolResult（不阻止工具）
        self.assertIsNone(result)
        # 验证：发送了UI提醒
        self.assertEqual(len(ui_log_calls), 1)
        self.assertEqual(ui_log_calls[0].level, "WARNING")
        self.assertIn("缓存命中率低时清理上下文", ui_log_calls[0].content)

    async def test_cache_ratio_reminder_yellow_state_low_cache(self):
        """测试黄灯状态且缓存命中率低于80%时发送提醒。"""
        # 设置黄灯状态（使用率85%）和低缓存比例（70%）
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.cumulative_token_usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 700,
            "output_tokens": 0,
        }

        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 85000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.85,
        }

        # 更新agent的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟清理工具调用
        from linhai.agent.orchestration import RedStateToolBlockPlugin

        plugin = RedStateToolBlockPlugin(self.registry)

        # 捕获UI日志
        ui_log_calls = []

        async def mock_send_ui_log(event_name, ui_notice):
            ui_log_calls.append(ui_notice)

        self.registry.send_if_exists = AsyncMock(side_effect=mock_send_ui_log)

        # 调用before_toolcall，应该发送提醒但不阻止工具
        result = await plugin.before_toolcall(
            tool_name="context_forget_range_step1",
            toolcall_arguments={},
            with_secret=None,
        )

        # 验证：不应返回FailedToolResult（不阻止工具）
        self.assertIsNone(result)
        # 验证：发送了UI提醒
        self.assertEqual(len(ui_log_calls), 1)
        self.assertEqual(ui_log_calls[0].level, "WARNING")
        self.assertIn("缓存命中率低时清理上下文", ui_log_calls[0].content)

    async def test_no_cache_ratio_reminder_when_cache_high(self):
        """测试缓存命中率高时不发送提醒。"""
        # 设置绿灯状态和高缓存比例（95%）
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.cumulative_token_usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 950,
            "output_tokens": 0,
        }

        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5,
        }

        # 更新agent的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟清理工具调用
        from linhai.agent.orchestration import RedStateToolBlockPlugin

        plugin = RedStateToolBlockPlugin(self.registry)

        # 捕获UI日志
        ui_log_calls = []

        async def mock_send_ui_log(event_name, ui_notice):
            ui_log_calls.append(ui_notice)

        self.registry.send_if_exists = AsyncMock(side_effect=mock_send_ui_log)

        # 调用before_toolcall，不应发送提醒
        result = await plugin.before_toolcall(
            tool_name="context_forget_large_message",
            toolcall_arguments={},
            with_secret=None,
        )

        # 验证：不应返回FailedToolResult
        self.assertIsNone(result)
        # 验证：没有发送UI提醒
        self.assertEqual(len(ui_log_calls), 0)

    async def test_no_cache_ratio_reminder_when_abnormally_low(self):
        """测试缓存命中率异常低（<5%）时不发送提醒，符合issue #991要求。"""
        # 设置绿灯状态和异常低缓存比例（0%）
        token_manager = self.registry.get_member_typechecked(
            "token_manager", TokenManager
        )
        token_manager.cumulative_token_usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 0,  # 0%缓存命中率
            "output_tokens": 0,
        }

        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 50000,
            "remaining_tokens": 50000,
            "usage_ratio": 0.5,
        }

        # 更新agent的threshold_info
        from linhai.agent.main import Agent

        mock_agent = self.registry.get_member_typechecked("agent", Agent)
        mock_agent.get_threshold_info = Mock(return_value=threshold_info)

        # 模拟清理工具调用
        from linhai.agent.orchestration import RedStateToolBlockPlugin

        plugin = RedStateToolBlockPlugin(self.registry)

        # 捕获UI日志
        ui_log_calls = []

        async def mock_send_ui_log(event_name, ui_notice):
            ui_log_calls.append(ui_notice)

        self.registry.send_if_exists = AsyncMock(side_effect=mock_send_ui_log)

        # 调用before_toolcall，不应发送提醒（因为缓存命中率低于5%）
        result = await plugin.before_toolcall(
            tool_name="context_forget_large_message",
            toolcall_arguments={},
            with_secret=None,
        )

        # 验证：不应返回FailedToolResult
        self.assertIsNone(result)
        # 验证：没有发送UI提醒（因为缓存命中率低于5%被视为异常）
        self.assertEqual(len(ui_log_calls), 0)
