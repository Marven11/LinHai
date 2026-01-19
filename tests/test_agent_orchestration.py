"""AgentContextOrchestration类的单元测试。"""

import unittest
import time
from unittest.mock import Mock, patch

from linhai.agent.orchestration import AgentContextOrchestration, ThresholdInfo
from linhai.agent.message import AgentMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat


class TestAgentContextOrchestration(unittest.IsolatedAsyncioTestCase):
    """AgentContextOrchestration类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        group_chat = GroupChat()
        # 注册一个mock的lifecycle以避免RuntimeError
        from linhai.agent.lifecycle import Lifecycle
        from linhai.tool.main import ToolManager

        mock_lifecycle = Mock(spec=Lifecycle)
        group_chat.register_member("lifecycle", mock_lifecycle)

        # 注册一个mock的tool_manager，因为SystemMessage初始化需要它
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        group_chat.register_member("tool_manager", mock_tool_manager)

        self.init_messages = [
            SystemMessage(
                group_chat=group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(group_chat, self.init_messages)
        self.orchestration = AgentContextOrchestration(
            group_chat, self.message_processor
        )

    async def test_context_thanox(self):
        """测试随机删除历史消息。"""
        for i in range(10):
            self.message_processor.add_new_message(UserMessage(message=f"Message {i}"))

        original_count = len(self.message_processor.get_messages())
        result = await self.orchestration.context_thanox()

        self.assertIn("context_thanox", result)
        self.assertLess(len(self.message_processor.get_messages()), original_count)

    async def test_context_thanox_insufficient_messages(self):
        """测试消息不足时的不删除。"""
        result = await self.orchestration.context_thanox()
        self.assertEqual(result, "消息数量不足，无需删除")

    def test_add_soft_threshold_notification(self):
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
        self.message_processor.add_new_message(large_msg)

        # 调用add_soft_threshold_notification，现在返回字符串
        result = self.orchestration.add_soft_threshold_notification(threshold_info)

        # 验证返回值
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("黄灯状态", result)
        self.assertIn("上下文占用量", result)
        self.assertIn("条大消息", result)
        # 消息数量应该仍然是3，因为通知没有被添加，只是返回
        self.assertEqual(len(self.message_processor.messages), 3)

    def test_add_soft_threshold_notification_with_compress_tool(self):
        """测试压缩工具调用后不添加通知。"""
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 60000,
            "remaining_tokens": 40000,
            "usage_ratio": 0.6,
        }
        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        self.message_processor.add_new_message(large_msg)

        # 模拟最近调用过清理工具
        self.orchestration.last_compress_or_clean_time = time.time() - 30

        # 调用add_soft_threshold_notification，现在返回字符串
        result = self.orchestration.add_soft_threshold_notification(threshold_info)

        # 对于绿灯状态且最近调用过清理工具，应该返回消息字符串
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("绿灯状态", result)
        self.assertIn("一分钟内有调用过消息清理工具", result)
        # 消息数量应该仍然是3
        self.assertEqual(len(self.message_processor.messages), 3)

    @patch("linhai.agent.message.Path")
    @patch("linhai.agent.message.json")
    async def test_save_conversation_history(self, _mock_json, mock_path):
        """测试保存对话历史。"""
        mock_home = Mock()
        mock_home.__truediv__ = Mock(return_value=mock_home)  # 链式调用返回自己
        mock_path.home.return_value = mock_home
        mock_home.mkdir.return_value = None

        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.write = Mock()

        mock_open = Mock(return_value=mock_file)

        with patch("builtins.open", mock_open):
            await self.message_processor.save_conversation_history()

        mock_home.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_open.assert_called_once()

    def test_get_status_display_piece(self):
        """测试获取状态显示片段。"""
        self.message_processor.add_new_message(RuntimeMessage("test"))

        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.large_messages.add(large_msg)
        self.message_processor.add_new_message(large_msg)

        # 不再需要标记垃圾，因为功能已删除

        # 测试不使用nerd font
        pieces = self.orchestration.get_status_display_pieces(use_nerd_font=False)
        self.assertIsInstance(pieces, list)
        self.assertGreater(len(pieces), 0)
        # 应该包含消息计数 - 格式已改为 '4 msgs', '1 large'
        for piece in pieces:
            if "msgs" in piece:
                self.assertIn("4", piece)  # 消息数量
            elif "large" in piece:
                self.assertIn("1", piece)  # 大消息数量

        # 测试使用nerd font
        nerd_pieces = self.orchestration.get_status_display_pieces(use_nerd_font=True)
        self.assertIsInstance(nerd_pieces, list)
        self.assertGreater(len(nerd_pieces), 0)
        # nerd字体使用图标，所以我们检查是否包含消息数量
        for piece in nerd_pieces:
            if "\uf27a" in piece:  # 消息图标
                self.assertIn("4", piece)  # 消息数量
            elif "\uf1c0" in piece:  # 大消息图标
                self.assertIn("1", piece)

    def test_determine_tool_category(self):
        """测试工具分类判断。"""
        # 测试消息清理工具
        self.assertEqual(
            self.orchestration._determine_tool_category("context_range_compress"),
            "cleanup",
        )
        self.assertEqual(
            self.orchestration._determine_tool_category("context_garbage_clean"),
            "cleanup",
        )
        self.assertEqual(
            self.orchestration._determine_tool_category("context_thanox"), "cleanup"
        )

        # context_mark_message_todelete 工具已删除，不再测试

        # 测试其他工具
        self.assertEqual(
            self.orchestration._determine_tool_category("read_file"), "other"
        )

    def test_determine_threshold_state(self):
        """测试阈值状态判断。"""
        self.assertEqual(self.orchestration._determine_threshold_state(0.3), "绿灯")
        self.assertEqual(self.orchestration._determine_threshold_state(0.55), "绿灯")
        self.assertEqual(self.orchestration._determine_threshold_state(0.75), "黄灯")
        self.assertEqual(self.orchestration._determine_threshold_state(0.95), "红灯")

    def test_recently_called_cleanup_tool(self):
        """测试最近调用清理工具判断。"""
        # 初始状态应该为False
        self.assertFalse(self.orchestration._recently_called_cleanup_tool())

        # 设置调用时间
        self.orchestration.last_compress_or_clean_time = time.time() - 30  # 30秒前
        self.assertTrue(self.orchestration._recently_called_cleanup_tool())

        # 超过一分钟
        self.orchestration.last_compress_or_clean_time = time.time() - 70  # 70秒前
        self.assertFalse(self.orchestration._recently_called_cleanup_tool())

    def test_red_state_with_recent_cleanup_allows_normal_tools(self):
        """测试红灯状态下，如果最近调用过清理工具，正常工具应该被允许。"""

        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 模拟最近调用过清理工具（30秒前）
        self.orchestration.last_compress_or_clean_time = time.time() - 30

        # 测试正常工具（如read_file）不应该被阻塞
        details = self.orchestration.get_tool_block_details("read_file", threshold_info)

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：最近调用过清理工具
        self.assertTrue(details["recently_called_cleanup"])
        # 验证：工具类别是other
        self.assertEqual(details["actual_category"], "other")
        # 验证：阻塞的类别应该是cleanup（只阻塞清理工具，不阻塞正常工具）
        self.assertEqual(details["blocked_category"], "cleanup")
        # 验证：因为blocked_category是cleanup，而actual_category是other，所以不应该被拦截
        self.assertNotEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_without_recent_cleanup_blocks_normal_tools(self):
        """测试红灯状态下，如果没有调用过清理工具，正常工具应该被阻塞。"""

        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 确保没有最近调用清理工具（超过70秒）
        self.orchestration.last_compress_or_clean_time = time.time() - 70

        # 测试正常工具（如read_file）应该被阻塞
        details = self.orchestration.get_tool_block_details("read_file", threshold_info)

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：最近没有调用过清理工具
        self.assertFalse(details["recently_called_cleanup"])
        # 验证：工具类别是other
        self.assertEqual(details["actual_category"], "other")
        # 验证：阻塞的类别应该是other（阻塞正常工具）
        self.assertEqual(details["blocked_category"], "other")
        # 验证：因为blocked_category和actual_category都是other，所以应该被拦截
        self.assertEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_with_recent_cleanup_blocks_cleanup_tools(self):
        """测试红灯状态下，如果最近调用过清理工具，清理工具应该被阻塞。"""
        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 模拟最近调用过清理工具（30秒前）
        self.orchestration.last_compress_or_clean_time = time.time() - 30

        # 测试清理工具（如context_garbage_clean）应该被阻塞
        details = self.orchestration.get_tool_block_details(
            "context_garbage_clean", threshold_info
        )

        # 验证：当前状态应该是红灯
        self.assertEqual(details["current_state"], "红灯")
        # 验证：最近调用过清理工具
        self.assertTrue(details["recently_called_cleanup"])
        # 验证：工具类别是cleanup
        self.assertEqual(details["actual_category"], "cleanup")
        # 验证：阻塞的类别应该是cleanup（阻塞清理工具）
        self.assertEqual(details["blocked_category"], "cleanup")
        # 验证：因为blocked_category和actual_category都是cleanup，所以应该被拦截
        self.assertEqual(details["blocked_category"], details["actual_category"])

    def test_red_state_with_recent_cleanup_error_message(self):
        """测试红灯状态下，最近调用过清理工具时返回正确的错误消息。"""
        # 设置红灯状态（使用率95%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 95000,
            "remaining_tokens": 5000,
            "usage_ratio": 0.95,
        }

        # 模拟最近调用过清理工具（30秒前）
        self.orchestration.last_compress_or_clean_time = time.time() - 30

        # 获取工具拦截详情
        details = self.orchestration.get_tool_block_details(
            "context_garbage_clean", threshold_info
        )

        # 验证应该被拦截
        self.assertEqual(details["blocked_category"], details["actual_category"])

        # 注意：实际错误消息由RedStateToolBlockPlugin生成，这里我们验证拦截逻辑正确
        # 具体的错误消息测试需要在RedStateToolBlockPlugin的测试中完成
        # 但我们可以验证拦截条件满足
        self.assertTrue(details["recently_called_cleanup"])
        self.assertEqual(details["current_state"], "红灯")
        self.assertEqual(details["actual_category"], "cleanup")

    def test_yellow_state_with_recent_cleanup_blocks_cleanup_tools(self):
        """测试黄灯状态下，如果最近调用过清理工具，清理工具应该被阻塞。"""

        # 设置黄灯状态（使用率75%）
        threshold_info: ThresholdInfo = {
            "hard_limit": 100000,
            "used_tokens": 75000,
            "remaining_tokens": 25000,
            "usage_ratio": 0.75,
        }

        # 模拟最近调用过清理工具（30秒前）
        self.orchestration.last_compress_or_clean_time = time.time() - 30

        # 测试清理工具（如context_garbage_clean）应该被阻塞
        details = self.orchestration.get_tool_block_details(
            "context_garbage_clean", threshold_info
        )

        # 验证：当前状态应该是黄灯
        self.assertEqual(details["current_state"], "黄灯")
        # 验证：最近调用过清理工具
        self.assertTrue(details["recently_called_cleanup"])
        # 验证：工具类别是cleanup
        self.assertEqual(details["actual_category"], "cleanup")
        # 验证：阻塞的类别应该是cleanup（阻塞清理工具）
        self.assertEqual(details["blocked_category"], "cleanup")
        # 验证：因为blocked_category和actual_category都是cleanup，所以应该被拦截
        self.assertEqual(details["blocked_category"], details["actual_category"])
