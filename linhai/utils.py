from typing import Literal
from pydantic import BaseModel

class CliRuntimeMessage(BaseModel):
    """运行时消息数据模型"""
    level: Literal["INFO", "WARNING", "ERROR"]
    content: str
