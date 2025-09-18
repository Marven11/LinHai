"""计算器工具模块，提供安全的数学计算功能。"""

import re
from linhai.tool.base import register_tool, ToolArgInfo


@register_tool(
    name="safe_calculator",
    desc="安全计算数学表达式。表达式只能包含数字、加减乘除符号(+ - * /)、乘方(**)、取模(%)、大于小于(> <)和空格。建议在计算任何数字时优先使用此工具。",
    args={
        "expression": ToolArgInfo(
            desc="数学表达式，例如 '2 + 3 * 4' 或 '10 % 3'", type="str"
        ),
    },
    required_args=["expression"],
)
def safe_calculator(expression: str) -> str:
    """安全计算数学表达式。只允许安全字符，避免代码执行。

    Args:
        expression: 数学表达式字符串

    Returns:
        计算结果字符串或错误消息
    """
    # 验证表达式只包含安全字符
    safe_pattern = r"^[0-9+\-*/().%><\s]+$"  # 允许数字、运算符、括号、点、空格
    if not re.match(safe_pattern, expression):
        return "错误: 表达式包含不安全字符。只允许数字、加减乘除(+ - * /)、乘方(**)、取模(%)、大于小于(> <)、括号和空格。"

    # 检查表达式是否为空或只包含空格
    if not expression.strip():
        return "错误: 表达式不能为空。"

    try:
        # 使用eval计算表达式，但捕获异常
        result = eval(expression, {"__builtins__": {}}, {})  # 限制内置函数和变量
        return str(result)
    except Exception as e:
        return f"错误: 计算失败 - {str(e)}"
