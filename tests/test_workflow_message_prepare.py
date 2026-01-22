"""测试workflow模块中的消息准备功能。"""

import unittest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any


# 模拟agent和message_processor
def create_mock_agent(messages: List[Dict[str, Any]]) -> Mock:
    """创建模拟的agent对象"""
    agent = Mock()
    message_processor = Mock()
    message_processor.messages = []

    # 创建模拟消息对象
    for i, msg_data in enumerate(messages):
        msg = Mock()
        msg.to_llm_message.return_value = msg_data
        message_processor.messages.append(msg)

    agent.message_processor = message_processor
    return agent


def extract_displayed_ids(result: str) -> List[int]:
    """从结果字符串中提取显示的ID列表"""
    ids = []
    for line in result.split("\n"):
        if line.startswith("- id:"):
            # 解析格式: "- id: 0 role: ..."
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "-" and parts[1] == "id:":
                try:
                    ids.append(int(parts[2]))
                except ValueError:
                    continue
    return ids


class TestPrepareMessagesForCompression(unittest.TestCase):
    """测试_prepare_messages_for_compression函数"""

    def setUp(self):
        # 导入待测试的函数
        from linhai.agent.workflow import _prepare_messages_for_compression

        self.prepare_func = _prepare_messages_for_compression

    def test_less_than_200_messages(self):
        """测试消息数小于200的情况：应显示所有消息"""
        # 创建199条模拟消息
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(199)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        # 应该显示所有199条消息
        self.assertEqual(len(displayed_ids), 199)
        # ID应该是连续的0-198
        self.assertEqual(displayed_ids, list(range(199)))

    def test_exactly_200_messages(self):
        """测试正好200条消息的情况：应间隔显示，显示数量严格少于200条"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(200)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        # 显示数量应严格少于200条
        self.assertLess(len(displayed_ids), 200)
        # 间隔应为2，显示100条消息
        self.assertEqual(len(displayed_ids), 100)
        # 应该显示偶数ID（0, 2, 4, ... 198）
        expected_ids = list(range(0, 200, 2))
        self.assertEqual(displayed_ids, expected_ids)

    def test_201_messages(self):
        """测试201条消息的情况：间隔应为2，显示101条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(201)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        self.assertEqual(len(displayed_ids), 101)  # ceil(201/2) = 101
        expected_ids = list(range(0, 201, 2))
        self.assertEqual(displayed_ids, expected_ids)

    def test_399_messages(self):
        """测试399条消息（区间[200, 400)的上界）：
        基础间隔应为2（按区间规则），但显示200条违反"少于200条"规则，
        因此实际间隔应为3，显示133条消息
        """
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(399)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        # 399条消息，间隔2会显示200条（违反规则），所以算法会调整为间隔3，显示133条
        self.assertEqual(len(displayed_ids), 133)
        # 间隔应为3
        expected_ids = list(range(0, 399, 3))
        self.assertEqual(displayed_ids, expected_ids)

    def test_400_messages(self):
        """测试400条消息（区间[400, 600)的下界）：间隔应为3，显示134条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(400)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        # ceil(400/3) = 134
        self.assertEqual(len(displayed_ids), 134)
        expected_ids = list(range(0, 400, 3))
        self.assertEqual(displayed_ids, expected_ids)

    def test_599_messages(self):
        """测试599条消息（区间[400, 600)的上界）：间隔应为4，显示150条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(599)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        # 算法会确保显示数量少于200条，间隔可能调整为4
        # 599/4 = 149.75，ceil后150
        self.assertEqual(len(displayed_ids), 150)
        expected_ids = list(range(0, 599, 4))
        self.assertEqual(displayed_ids, expected_ids)

    def test_600_messages(self):
        """测试600条消息（区间[600, 800)的下界）：间隔应为4，显示150条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(600)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        self.assertEqual(len(displayed_ids), 150)  # 600/4 = 150
        expected_ids = list(range(0, 600, 4))
        self.assertEqual(displayed_ids, expected_ids)

    def test_799_messages(self):
        """测试799条消息（区间[600, 800)的上界）：间隔应为5，显示160条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(799)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        # 799/5 = 159.8，ceil后160
        self.assertEqual(len(displayed_ids), 160)
        expected_ids = list(range(0, 799, 5))
        self.assertEqual(displayed_ids, expected_ids)

    def test_1000_messages(self):
        """测试1000条消息：间隔应为6，显示167条消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(1000)]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        displayed_ids = extract_displayed_ids(result)

        self.assertLess(len(displayed_ids), 200)
        # 1000/6 ≈ 166.67，ceil后167
        self.assertEqual(len(displayed_ids), 167)
        expected_ids = list(range(0, 1000, 6))
        self.assertEqual(displayed_ids, expected_ids)

    def test_message_content_format(self):
        """测试消息内容的格式化是否正确"""
        messages = [
            {"role": "user", "content": "Hello World"},
            {"role": "assistant", "content": None},  # 测试None内容
            {"role": "system", "content": "System message"},
        ]
        agent = create_mock_agent(messages)

        result = self.prepare_func(agent)
        lines = result.split("\n")

        # 应该有3行
        self.assertEqual(len(lines), 3)

        # 检查每行格式
        self.assertIn("id: 0", lines[0])
        self.assertIn("role: 'user'", lines[0])
        self.assertIn("content: 'Hello World'", lines[0])

        self.assertIn("id: 1", lines[1])
        self.assertIn("role: 'assistant'", lines[1])
        self.assertIn("content: None", lines[1])

        self.assertIn("id: 2", lines[2])
        self.assertIn("role: 'system'", lines[2])
        self.assertIn("content: 'System message'", lines[2])


if __name__ == "__main__":
    unittest.main()
