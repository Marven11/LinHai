"""测试token缓存估算功能。"""

import unittest
from unittest.mock import MagicMock
from linhai.llm import OpenAi, UserMessage, AssistantMessage, AnswerTokenUsage


class TestTokenCache(unittest.TestCase):
    """测试token缓存估算。"""

    def setUp(self):
        """设置测试环境。"""
        # 创建Mock的group_chat参数
        mock_group_chat = MagicMock()
        self.openai = OpenAi(
            group_chat=mock_group_chat,
            api_key="test_key",
            base_url="https://api.example.com",
            model="test-model",
            openai_config={},
            chat_completion_kwargs={},
            name="test-llm",
            support_image=False,
            explicit_cache_info=None,
        )

    def test_calculate_cache_estimation(self):
        """测试缓存估算计算。"""
        msg1 = UserMessage(message="Hello")
        msg2 = AssistantMessage(message="Hi there")

        self.openai.previous_history = [msg1, msg2]
        self.openai.previous_input_tokens = 100

        current_history = [msg1, msg2]

        same_prefix_chars = 0
        previous_total_chars = 0

        for msg in self.openai.previous_history:
            llm_msg = msg.to_llm_message()
            if "content" in llm_msg and llm_msg["content"]:
                previous_total_chars += len(str(llm_msg["content"]))

        min_len = min(len(current_history), len(self.openai.previous_history))
        for i in range(min_len):
            current_msg = current_history[i].to_llm_message()
            previous_msg = self.openai.previous_history[i].to_llm_message()

            current_content = current_msg.get("content", "")
            previous_content = previous_msg.get("content", "")

            if current_content == previous_content:
                same_prefix_chars += len(str(current_content))
            else:
                break

        cached_input_tokens = 0
        if previous_total_chars > 0:
            cached_input_tokens = int(
                self.openai.previous_input_tokens
                * (same_prefix_chars / previous_total_chars)
            )

        self.assertEqual(cached_input_tokens, 100)  # 完全相同时应该100%缓存

    def test_cache_estimation_with_different_history(self):
        """测试不同history的缓存估算。"""
        prev_msg1 = UserMessage(message="Hello")
        prev_msg2 = AssistantMessage(message="Hi there")

        current_msg1 = UserMessage(message="Hello")
        current_msg2 = AssistantMessage(message="Different response")

        self.openai.previous_history = [prev_msg1, prev_msg2]
        self.openai.previous_input_tokens = 100

        current_history = [current_msg1, current_msg2]

        same_prefix_chars = 0
        previous_total_chars = 0

        for msg in self.openai.previous_history:
            llm_msg = msg.to_llm_message()
            if "content" in llm_msg and llm_msg["content"]:
                previous_total_chars += len(str(llm_msg["content"]))

        min_len = min(len(current_history), len(self.openai.previous_history))
        for i in range(min_len):
            current_msg = current_history[i].to_llm_message()
            previous_msg = self.openai.previous_history[i].to_llm_message()

            current_content = current_msg.get("content", "")
            previous_content = previous_msg.get("content", "")

            if current_content == previous_content:
                same_prefix_chars += len(str(current_content))
            else:
                break

        cached_input_tokens = 0
        if previous_total_chars > 0:
            cached_input_tokens = int(
                self.openai.previous_input_tokens
                * (same_prefix_chars / previous_total_chars)
            )

        self.assertGreater(cached_input_tokens, 0)
        self.assertLess(cached_input_tokens, 100)

    def test_answer_token_usage_with_cache(self):
        """测试包含缓存token的AnswerTokenUsage。"""
        token_usage = AnswerTokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cached_input_tokens=25,
        )

        self.assertEqual(token_usage.input_tokens, 100)
        self.assertEqual(token_usage.output_tokens, 50)
        self.assertEqual(token_usage.total_tokens, 150)
        self.assertEqual(token_usage.cached_input_tokens, 25)


if __name__ == "__main__":
    unittest.main()
