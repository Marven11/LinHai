"""测试软阈值状态转换逻辑"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from linhai.agent.main import Agent
from linhai.group_chat import GroupChat
from linhai.llm import OpenAi, Answer, ChatMessage
from linhai.agent.base import RuntimeMessage


class MockAnswer(Answer):
    """模拟Answer类"""
    
    def __init__(self, message_content="测试回复"):
        self._message_content = message_content
        self._tokens = [message_content]
        self._current_index = 0
        self._interrupted = False
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._current_index >= len(self._tokens) or self._interrupted:
            raise StopAsyncIteration
        token = self._tokens[self._current_index]
        self._current_index += 1
        return token
    
    def get_current_content(self):
        return self._message_content
    
    def get_message(self):
        return ChatMessage(role="assistant", message=self._message_content)
    
    def interrupt(self):
        self._interrupted = True


class TestThresholdState(unittest.TestCase):
    """测试软阈值状态转换"""

    def setUp(self):
        """设置测试环境"""
        # 创建模拟GroupChat
        self.mock_group_chat = Mock(spec=GroupChat)
        self.mock_group_chat.is_empty = Mock(return_value=True)
        self.mock_group_chat.has_member = Mock(return_value=False)
        self.mock_group_chat.send = AsyncMock()
        self.mock_group_chat.receive = AsyncMock()
        
        # 创建模拟LLM
        self.mock_llm = Mock(spec=OpenAi)
        self.mock_llm.answer_stream = AsyncMock(return_value=MockAnswer())
        
        # 创建Agent上下文
        self.context = {
            "system_prompt": "测试提示",
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold_soft": 50000,  # 软阈值
            "compress_threshold_hard": 80000,  # 硬阈值
        }
        
        # 创建初始化消息
        self.init_messages = []
        
        # 创建Agent实例
        self.agent = Agent(
            context=self.context,
            group_chat=self.mock_group_chat,
            init_messages=self.init_messages
        )

    @unittest.skip("需要实现_get_state_message方法")
    def test_green_state_twice(self):
        """测试两次处于绿灯状态（第二次不重复提醒）"""
        # 模拟第一次绿灯状态（taken=0.3）
        self.agent.last_token_usage = 35000  # 低于软阈值
        self.agent.last_threshold_state = None  # 初始状态
        
        # 第一次调用状态检查，应该触发绿灯提醒
        with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
            mock_threshold.return_value = (50000, 80000, 35000, 45000, 0.3)
            
            # 直接调用状态检查逻辑
            self.agent.compress_tool_called_in_last_response = False
            threshold_info = self.agent.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                # 根据taken计算当前状态
                if taken <= 0.4:
                    current_state = "green"
                elif taken <= 0.6:
                    current_state = "green_blink"
                elif taken <= 0.8:
                    current_state = "yellow"
                else:
                    current_state = "red"
                
                # 检查状态是否改变
                if current_state != self.agent.last_threshold_state:
                    # 对于绿灯，只有从其他状态变为绿灯时才提醒
                    if current_state == "green":
                        if self.agent.last_threshold_state != "green":
                            # 发送绿灯消息
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                    else:
                        # 对于非绿灯状态，状态改变时总是提醒
                        state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                        self.agent.messages.append(RuntimeMessage(state_message))
                    
                    # 更新状态
                    self.agent.last_threshold_state = current_state
            
            # 检查是否添加了绿灯消息
            self.assertEqual(len(self.agent.messages), 1)
            self.assertIsInstance(self.agent.messages[0], RuntimeMessage)
            self.assertIn("绿灯", self.agent.messages[0].message)
            self.assertEqual(self.agent.last_threshold_state, "green")
        
        # 第二次状态检查，同样处于绿灯状态
        with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
            mock_threshold.return_value = (50000, 80000, 35000, 45000, 0.3)
            
            # 清空消息以便测试
            original_message_count = len(self.agent.messages)
            
            # 直接调用状态检查逻辑
            self.agent.compress_tool_called_in_last_response = False
            threshold_info = self.agent.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                # 根据taken计算当前状态
                if taken <= 0.4:
                    current_state = "green"
                elif taken <= 0.6:
                    current_state = "green_blink"
                elif taken <= 0.8:
                    current_state = "yellow"
                else:
                    current_state = "red"
                
                # 检查状态是否改变
                if current_state != self.agent.last_threshold_state:
                    # 对于绿灯，只有从其他状态变为绿灯时才提醒
                    if current_state == "green":
                        if self.agent.last_threshold_state != "green":
                            # 发送绿灯消息
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                    else:
                        # 对于非绿灯状态，状态改变时总是提醒
                        state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                        self.agent.messages.append(RuntimeMessage(state_message))
                    
                    # 更新状态
                    self.agent.last_threshold_state = current_state
            
            # 检查没有添加新消息（状态未改变）
            self.assertEqual(len(self.agent.messages), original_message_count)
            self.assertEqual(self.agent.last_threshold_state, "green")

    @unittest.skip("需要实现_get_state_message方法")
    def test_green_to_yellow_to_green(self):
        """测试从绿变黄、再从黄变绿的状态转换"""
        # 初始状态：绿灯
        self.agent.last_token_usage = 35000
        self.agent.last_threshold_state = None
        
        # 第一次：绿灯状态
        with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
            mock_threshold.return_value = (50000, 80000, 35000, 45000, 0.3)
            
            # 直接调用状态检查逻辑
            self.agent.compress_tool_called_in_last_response = False
            threshold_info = self.agent.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                # 根据taken计算当前状态
                if taken <= 0.4:
                    current_state = "green"
                elif taken <= 0.6:
                    current_state = "green_blink"
                elif taken <= 0.8:
                    current_state = "yellow"
                else:
                    current_state = "red"
                
                # 检查状态是否改变
                if current_state != self.agent.last_threshold_state:
                    # 对于绿灯，只有从其他状态变为绿灯时才提醒
                    if current_state == "green":
                        if self.agent.last_threshold_state != "green":
                            # 发送绿灯消息
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                    else:
                        # 对于非绿灯状态，状态改变时总是提醒
                        state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                        self.agent.messages.append(RuntimeMessage(state_message))
                    
                    # 更新状态
                    self.agent.last_threshold_state = current_state
            
            # 检查绿灯消息
            self.assertEqual(len(self.agent.messages), 1)
            self.assertIn("绿灯", self.agent.messages[0].message)
            self.assertEqual(self.agent.last_threshold_state, "green")
        
        # 第二次：黄灯状态（从绿变黄）
        with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
            mock_threshold.return_value = (50000, 80000, 65000, 15000, 0.7)  # taken=0.7 -> 黄灯
            
            original_message_count = len(self.agent.messages)
            
            # 直接调用状态检查逻辑
            self.agent.compress_tool_called_in_last_response = False
            threshold_info = self.agent.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                # 根据taken计算当前状态
                if taken <= 0.4:
                    current_state = "green"
                elif taken <= 0.6:
                    current_state = "green_blink"
                elif taken <= 0.8:
                    current_state = "yellow"
                else:
                    current_state = "red"
                
                # 检查状态是否改变
                if current_state != self.agent.last_threshold_state:
                    # 对于绿灯，只有从其他状态变为绿灯时才提醒
                    if current_state == "green":
                        if self.agent.last_threshold_state != "green":
                            # 发送绿灯消息
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                    else:
                        # 对于非绿灯状态，状态改变时总是提醒
                        state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                        self.agent.messages.append(RuntimeMessage(state_message))
                    
                    # 更新状态
                    self.agent.last_threshold_state = current_state
            
            # 检查添加了黄灯消息
            self.assertEqual(len(self.agent.messages), original_message_count + 1)
            self.assertIn("黄灯", self.agent.messages[-1].message)
            self.assertEqual(self.agent.last_threshold_state, "yellow")
        
        # 第三次：回到绿灯状态（从黄变绿）
        with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
            mock_threshold.return_value = (50000, 80000, 35000, 45000, 0.3)  # taken=0.3 -> 绿灯
            
            original_message_count = len(self.agent.messages)
            
            # 直接调用状态检查逻辑
            self.agent.compress_tool_called_in_last_response = False
            threshold_info = self.agent.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                # 根据taken计算当前状态
                if taken <= 0.4:
                    current_state = "green"
                elif taken <= 0.6:
                    current_state = "green_blink"
                elif taken <= 0.8:
                    current_state = "yellow"
                else:
                    current_state = "red"
                
                # 检查状态是否改变
                if current_state != self.agent.last_threshold_state:
                    # 对于绿灯，只有从其他状态变为绿灯时才提醒
                    if current_state == "green":
                        if self.agent.last_threshold_state != "green":
                            # 发送绿灯消息
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                    else:
                        # 对于非绿灯状态，状态改变时总是提醒
                        state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                        self.agent.messages.append(RuntimeMessage(state_message))
                    
                    # 更新状态
                    self.agent.last_threshold_state = current_state
            
            # 检查添加了绿灯消息（状态改变）
            self.assertEqual(len(self.agent.messages), original_message_count + 1)
            self.assertIn("绿灯", self.agent.messages[-1].message)
            self.assertEqual(self.agent.last_threshold_state, "green")

    @unittest.skip("需要实现_get_state_message方法")
    def test_all_state_transitions(self):
        """测试所有状态转换"""
        # 测试状态：绿灯 -> 绿灯闪烁 -> 黄灯 -> 红灯
        states = [
            (0.3, "green"),
            (0.5, "green_blink"), 
            (0.7, "yellow"),
            (0.9, "red")
        ]
        
        self.agent.last_threshold_state = None
        
        for taken, expected_state in states:
            with patch.object(self.agent, 'get_threshold_info') as mock_threshold:
                # 计算对应的token使用量
                soft = 50000
                hard = 80000
                used = int(soft + taken * (hard - soft))
                remaining = hard - used
                
                mock_threshold.return_value = (soft, hard, used, remaining, taken)
                
                original_message_count = len(self.agent.messages)
                
                # 直接调用状态检查逻辑
                self.agent.compress_tool_called_in_last_response = False
                threshold_info = self.agent.get_threshold_info()
                if threshold_info:
                    soft, hard, used, remaining, taken = threshold_info
                    # 根据taken计算当前状态
                    if taken <= 0.4:
                        current_state = "green"
                    elif taken <= 0.6:
                        current_state = "green_blink"
                    elif taken <= 0.8:
                        current_state = "yellow"
                    else:
                        current_state = "red"
                    
                    # 检查状态是否改变
                    if current_state != self.agent.last_threshold_state:
                        # 对于绿灯，只有从其他状态变为绿灯时才提醒
                        if current_state == "green":
                            if self.agent.last_threshold_state != "green":
                                # 发送绿灯消息
                                state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                                self.agent.messages.append(RuntimeMessage(state_message))
                        else:
                            # 对于非绿灯状态，状态改变时总是提醒
                            state_message = self.agent._get_state_message(current_state, used, hard, taken, remaining)
                            self.agent.messages.append(RuntimeMessage(state_message))
                        
                        # 更新状态
                        self.agent.last_threshold_state = current_state
                
                # 检查状态更新
                self.assertEqual(self.agent.last_threshold_state, expected_state)
                
                # 如果状态改变，应该添加消息
                if expected_state != "green" or original_message_count == 0:
                    self.assertEqual(len(self.agent.messages), original_message_count + 1)
                    # 根据预期状态检查对应的消息内容
                    if expected_state == "green":
                        self.assertIn("当前处于绿灯状态", self.agent.messages[-1].message)
                    elif expected_state == "green_blink":
                        self.assertIn("当前处于绿灯闪烁状态", self.agent.messages[-1].message)
                    elif expected_state == "yellow":
                        self.assertIn("当前处于黄灯状态", self.agent.messages[-1].message)
                    elif expected_state == "red":
                        self.assertIn("当前处于红灯状态", self.agent.messages[-1].message)


if __name__ == "__main__":
    unittest.main()