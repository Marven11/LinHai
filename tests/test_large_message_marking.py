import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.agent.message import AgentMessage
from linhai.group_chat import GroupChat
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.tool.base import ToolCallResultMessage
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.tool.main import ToolManager
from linhai.token_manager import TokenManager
from linhai.multimodal import ImageMessage


class TestLargeMessageMarking(unittest.IsolatedAsyncioTestCase):
    """大消息标记和清理功能的单元测试。"""

    def setUp(self):
        self.group_chat = GroupChat()
        
        # 注册必要的mock组件
        from linhai.agent.lifecycle import Lifecycle
        mock_lifecycle = Mock(spec=Lifecycle)
        self.group_chat.register_member("lifecycle", mock_lifecycle)
        
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.group_chat.register_member("tool_manager", mock_tool_manager)
        
        mock_token_manager = Mock(spec=TokenManager)
        mock_token_manager.get_large_message_reprs = Mock(return_value=[])
        mock_token_manager.cumulative_token_usage = None
        self.group_chat.register_member("token_manager", mock_token_manager)
        
        from pathlib import Path
        import tempfile
        temp_dir = tempfile.mkdtemp()
        conversation_folder = Path(temp_dir)
        self.group_chat.register_member("conversation_folder", conversation_folder)
        
        self.init_messages = [
            SystemMessage(group_chat=self.group_chat),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(self.group_chat, self.init_messages)
        self.orchestration = AgentContextOrchestration(
            self.group_chat, self.message_processor
        )

    async def test_mark_long_message(self):
        """测试长消息（token长度>800）被标记。"""
        # 模拟tiktoken编码，让消息的token长度超过800
        with patch("tiktoken.get_encoding") as mock_get_encoding:
            mock_encoder = Mock()
            # 模拟编码返回一个长列表，假设每个字符对应一个token
            mock_encoder.encode.return_value = list(range(1000))  # 1000个token
            mock_get_encoding.return_value = mock_encoder
            
            # 创建一个长消息（内容长度不重要，因为编码被模拟）
            long_message = RuntimeMessage("A" * 10)  # 内容很短，但编码返回1000个token
            
            # 触发_on_tool_result回调（模拟工具调用成功）
            await self.orchestration._on_tool_result(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=long_message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            # 验证消息被标记为大消息
            self.assertIn(long_message, self.orchestration.large_messages)
            self.assertEqual(len(self.orchestration.large_messages), 1)

    async def test_mark_image_message(self):
        """测试图片消息总是被标记。"""
        # 创建一个模拟的ImageMessage
        image_bytes = b"fake_image_data"
        mime_type = "image/png"
        filename = "test.png"
        image_message = ImageMessage(
            image_bytes=image_bytes,
            mime_type=mime_type,
            filename=filename,
            group_chat=self.group_chat,
        )
        
        # 触发_on_tool_result回调（模拟工具调用成功）
        await self.orchestration._on_tool_result(
            tool_name="test_tool",
            tool_index=0,
            status="success",
            message=image_message,
            toolcall_arguments={},
            with_secret=None,
            is_tool_failed_duplicated_error=False,
        )
        
        # 验证图片消息被标记为大消息
        self.assertIn(image_message, self.orchestration.large_messages)
        self.assertEqual(len(self.orchestration.large_messages), 1)

    async def test_do_not_mark_short_message(self):
        """测试短消息（token长度<=800）不被标记。"""
        with patch("tiktoken.get_encoding") as mock_get_encoding:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = list(range(500))  # 500个token
            mock_get_encoding.return_value = mock_encoder
            
            short_message = RuntimeMessage("Short message")
            
            await self.orchestration._on_tool_result(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=short_message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
            
            self.assertNotIn(short_message, self.orchestration.large_messages)
            self.assertEqual(len(self.orchestration.large_messages), 0)

    async def test_delete_large_messages(self):
        """测试删除大消息时，消息从数组中移除且其余消息不变。"""
        # 添加一些普通消息
        msg1 = UserMessage(message="Message 1")
        msg2 = UserMessage(message="Message 2")
        msg3 = AssistantMessage(message="Response 1")
        
        self.message_processor.add_new_message(msg1)
        self.message_processor.add_new_message(msg2)
        self.message_processor.add_new_message(msg3)
        
        # 添加5个大消息
        large_msgs = [RuntimeMessage(f"Large {i}") for i in range(5)]
        
        for msg in large_msgs:
            self.orchestration.large_messages.add(msg)
            self.message_processor.add_new_message(msg)
        
        # 初始消息总数：2个初始 + 3个普通 + 5个大 = 10个
        initial_messages = self.message_processor.messages.copy()
        
        # 模拟不足5条大消息（4条）
        with patch.object(self.orchestration, "large_messages", {"fake1", "fake2", "fake3", "fake4"}):
            result = await self.orchestration.context_garbage_clean()
            # 由于大消息数量不足5，应该返回失败
            self.assertIsInstance(result, ToolResultFailed)
            
        # 执行清理（现在有5条大消息）
        result = await self.orchestration.context_garbage_clean()
        self.assertIsInstance(result, ToolResultSuccess)
        
        # 验证大消息集合已清空
        self.assertEqual(len(self.orchestration.large_messages), 0)
        
        # 验证消息数组中不再包含大消息
        remaining_messages = self.message_processor.messages
        for msg in large_msgs:
            self.assertNotIn(msg, remaining_messages)
        
        # 验证其他消息保持不变
        self.assertIn(msg1, remaining_messages)
        self.assertIn(msg2, remaining_messages)
        self.assertIn(msg3, remaining_messages)
        
        # 验证消息顺序和数量
        # 初始消息有2个，加上3个普通消息，总共应该是5个
        self.assertEqual(len(remaining_messages), 5)


if __name__ == "__main__":
    unittest.main()