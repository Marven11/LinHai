"""用户输入解析模块，用于统一解析用户的各种输入格式。"""

from typing import Optional
from pydantic import BaseModel


class ParsedInput(BaseModel):
    """解析后的用户输入模型。"""
    switch_model: Optional[str] = None
    command: Optional[str] = None
    mentioned: list[str] = []


def parse_user_input(user_input: str) -> ParsedInput:
    """
    解析用户输入，提取switch_model、command和mentioned信息。
    
    参数:
        user_input: 用户输入的字符串
        
    返回:
        ParsedInput: 包含解析结果的模型
    """
    result = ParsedInput()
    
    # 按行分割输入
    lines = user_input.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # 解析命令（以/开头）
        if line.startswith('/') and not result.command:
            command_part = line[1:].strip()
            # 只取第一个单词作为命令
            if ' ' in command_part:
                result.command = command_part.split(' ')[0]
            else:
                result.command = command_part
            
        # 解析@提及（不处于开头的@）
        if '@' in line and not line.startswith('@'):
            # 找到所有@符号的位置
            at_positions = [i for i, char in enumerate(line) if char == '@']
            for pos in at_positions:
                if pos > 0:  # 不处于开头
                    # 提取@后面的名称
                    name_start = pos + 1
                    name_end = len(line)
                    for end_pos in range(name_start, len(line)):
                        if not line[end_pos].isalnum() and line[end_pos] not in ['_', '-']:
                            name_end = end_pos
                            break
                    mentioned_name = line[name_start:name_end]
                    if mentioned_name and mentioned_name not in result.mentioned:
                        result.mentioned.append(mentioned_name)
    
    return result