"""防止agent错误输出工具调用内容的插件。"""

import re
from linhai.agent.plugin import Plugin
from linhai.llm import Answer


class PreventToolOutputPlugin(Plugin):
    """防止agent错误输出工具调用内容的插件。
    
    当agent的第一个回复中有一行的开头是`**tool**`时打断agent，
    并提示不要输出工具调用的内容。
    """

    async def during_message_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        
        # 检查是否是第一个回复：消息历史中没有之前的agent消息
        has_previous_agent_message = any(
            msg.role == "assistant" 
            for msg in agent.message_processor.get_messages()
            if hasattr(msg, 'role')
        )
        
        # 如果是第一个回复且有一行的开头是`**tool**`，则打断
        if not has_previous_agent_message:
            # 检查是否有一行的开头是`**tool**`
            lines = current_content.split('\n')
            for line in lines:
                if line.strip().startswith('**tool**'):
                    await agent.interrupt(
                        "错误：请不要输出工具调用的内容！"
                        "工具调用内容（如`**tool**`）是系统内部使用的标签，"
                        "你不应该直接输出这些内容。"
                    )
                    return True
        
        return False

    def register(self, lifecycle):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)