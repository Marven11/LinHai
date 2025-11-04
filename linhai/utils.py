from typing import Literal
import secrets
from pydantic import BaseModel

class CliRuntimeNotice(BaseModel):
    """运行时消息数据模型"""
    level: Literal["INFO", "WARNING", "ERROR"]
    content: str

def generate_id(prefix: str) -> str:
    """生成指定格式的ID
    
    Args:
        prefix: ID前缀，如'terminal'、'largemessage'等
        
    Returns:
        格式为'<prefix>_<bytes>'的ID，其中bytes是12位hex
    """
    bytes_part = secrets.token_hex(6)  # 6字节 = 12位hex
    return f"{prefix}_{bytes_part}"
