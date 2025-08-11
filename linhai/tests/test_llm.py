import asyncio
import unittest
import timeout_decorator
from unittest.mock import AsyncMock, MagicMock, patch
from linhai.llm import OpenAi, ChatMessage


class TestLLM(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # 创建模拟的OpenAi实例
        self.llm = OpenAi(
            api_key="test_key",
            base_url="https://test.com",
            model="test_model",
            openai_config={},
        )

    def test_chat_message_creation(self):
        """测试ChatMessage类的创建和转换功能"""
        msg = ChatMessage(role="user", message="Hello")
        chat_msg = msg.to_llm_message()
        self.assertEqual(chat_msg.get("role"), "user")
        self.assertEqual(chat_msg.get("content"), "Hello")

    async def test_openai_answer_stream(self):
        """测试OpenAi answer_stream的基本功能"""
        # 创建完全mock的OpenAI客户端
        mock_client = MagicMock()

        # 创建模拟的流响应
        async def mock_stream():
            mock_chunk1 = MagicMock()
            mock_chunk1.choices = [MagicMock()]
            mock_chunk1.choices[0].delta.content = "Hello"
            await asyncio.sleep(0)  # 让出控制权
            yield mock_chunk1
            
            mock_chunk2 = MagicMock()
            mock_chunk2.choices = [MagicMock()]
            mock_chunk2.choices[0].delta.content = " World"
            await asyncio.sleep(0)  # 让出控制权
            yield mock_chunk2

        # 配置mock客户端返回我们的模拟流
        mock_client.chat.completions.create = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_stream()

        # 使用patch直接替换openai属性
        with patch.object(self.llm, 'openai', mock_client):
            # 运行测试，添加超时控制
            history = [ChatMessage(role="user", message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history),
                timeout=5.0
            )

            # 验证流式响应
            content = ""
            async for token in answer:
                content += token["content"]

            self.assertEqual(content, "Hello World")
            mock_client.chat.completions.create.assert_called_once()

    async def test_openai_answer_interrupt(self):
        """测试OpenAi answer_stream的中断功能"""
        # 创建完全mock的OpenAI客户端
        mock_client = MagicMock()

        # 创建模拟的流响应
        async def mock_stream():
            mock_chunk1 = MagicMock()
            mock_chunk1.choices = [MagicMock()]
            mock_chunk1.choices[0].delta.content = "Hello"
            yield mock_chunk1
            
            mock_chunk2 = MagicMock()
            mock_chunk2.choices = [MagicMock()]
            mock_chunk2.choices[0].delta.content = " World"
            yield mock_chunk2

        # 配置mock客户端返回我们的模拟流
        mock_client.chat.completions.create = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_stream()

        # 使用patch直接替换openai属性
        with patch.object(self.llm, 'openai', mock_client):
            # 运行测试，添加超时控制
            history = [ChatMessage(role="user", message="Hi")]
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history),
                timeout=5.0
            )

            # 收集流式响应并在中途中断
            content = ""
            token_count = 0
            async for token in answer:
                content += token["content"]
                token_count += 1
                if token_count == 2:
                    answer.interrupt()
                    break

            self.assertEqual(content, "Hello World")
            mock_client.chat.completions.create.assert_called_once()

    def test_openai_initialization(self):
        """测试OpenAi类的初始化"""
        self.assertEqual(self.llm.model, "test_model")

    @patch("openai.AsyncOpenAI")
    async def test_openai_error_handling(self, mock_openai_class):
        """测试错误处理情况"""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_openai_class.return_value = mock_client

        with self.assertRaises(Exception):
            history = [ChatMessage(role="user", message="Hi")]
            # 添加超时控制
            answer = await asyncio.wait_for(
                self.llm.answer_stream(history),
                timeout=5.0
            )
            async for _ in answer:
                pass


if __name__ == "__main__":
    unittest.main()
