#!/usr/bin/env python3
"""调试脚本：验证 /queue 消息处理"""

import asyncio
from unittest.mock import Mock, AsyncMock
from linhai.agent import Agent, AgentConfig
from linhai.group_chat import GroupChat
from linhai.llm import ChatMessage


class MockAnswer:
    """模拟 Answer 类"""
    def __init__(self):
        self.tokens = ["test", " token"]
        self.current_index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.current_index < len(self.tokens):
            token = self.tokens[self.current_index]
            self.current_index += 1
            return token
        raise StopAsyncIteration
    
    def get_current_content(self):
        return "".join(self.tokens[:self.current_index])
    
    def get_message(self):
        return ChatMessage(role="assistant", message="Agent response")
    
    def interrupt(self):
        pass


async def main():
    """主函数"""
    group_chat = GroupChat()
    
    # 创建模拟 LLM
    mock_llm = Mock()
    mock_answer = MockAnswer()
    mock_llm.answer_stream = AsyncMock(return_value=mock_answer)
    
    # 创建 Agent 配置
    config = AgentConfig(
        system_prompt="测试",
        llms=[mock_llm],
        llm_names=["test_llm"],
        current_llm_index=0,
        compress_threshold_soft=32768,
        compress_threshold_hard=52428,
    )
    
    # 注册 ToolManager
    from linhai.tool.main import ToolManager
    from linhai.tool.base import global_tools
    from linhai.tool.tools.terminal import terminal_toolset
    tool_manager = ToolManager(group_chat=group_chat, toolsets=[global_tools, terminal_toolset])
    
    # 创建 Agent 实例
    agent = Agent(config=config, group_chat=group_chat, init_messages=[])
    
    # 模拟 group_chat 行为
    group_chat.is_empty = Mock(return_value=False)
    group_chat.receive = AsyncMock(return_value=ChatMessage(role="user", message="/queue test message"))
    group_chat.send = AsyncMock()
    
    # 调用 generate_response
    await agent.generate_response()
    
    # 检查 queued_messages
    print(f"queued_messages: {agent.queued_messages}")
    print(f"Number of queued_messages: {len(agent.queued_messages)}")
    if agent.queued_messages:
        print(f"First message: {agent.queued_messages[0].message}")
    
    # 检查消息列表
    print(f"Total messages: {len(agent.messages)}")
    for i, msg in enumerate(agent.messages):
        print(f"Message {i}: {type(msg).__name__} - {getattr(msg, 'message', 'No message')}")


if __name__ == "__main__":
    asyncio.run(main())