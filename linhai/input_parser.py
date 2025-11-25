"""用户输入解析模块，用于统一解析用户的各种输入格式。"""

from typing import Optional
import re

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

    if user_input.startswith("/"):
        result.command = user_input.split().pop(0)[1:]
    if user_input.startswith("@"):
        result.switch_model = user_input.split().pop(0)[1:]
    result.mentioned = list(
        dict.fromkeys(
            result.group(1) for result in re.finditer("@([a-zA-Z-_]+)", user_input[1:])
        )
    )

    return result
