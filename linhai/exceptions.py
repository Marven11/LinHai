"""定义程序运行时的各类错误"""

from typing import Optional


class LinHaiError(Exception):
    """基础错误类"""

    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class ConfigValidationError(LinHaiError):
    """配置验证失败异常"""


__all__ = ["LinHaiError", "ConfigValidationError"]
