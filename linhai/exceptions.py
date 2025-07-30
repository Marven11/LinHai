"""定义程序运行时的各类错误"""
from typing import Optional

class LinHaiError(Exception):
    """基础错误类"""
    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)

class NetworkError(LinHaiError):
    """网络连接错误"""

class LLMResponseError(LinHaiError):
    """LLM输出格式错误"""

__all__ = [
    "LinHaiError",
    "NetworkError", 
    "LLMResponseError"
]
