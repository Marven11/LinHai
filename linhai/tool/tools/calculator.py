from typing import TypedDict
from linhai.tool.base import register_tool, ToolArgInfo

@register_tool(
    name="add_numbers",
    desc="计算两个数字的和",
    args={
        "a": ToolArgInfo(desc="第一个数字", type="float"),
        "b": ToolArgInfo(desc="第二个数字", type="float")
    },
    required_args=["a", "b"]
)
def add_numbers(a: float, b: float) -> float:
    """计算两个数字的和
    
    Args:
        a: 第一个数字
        b: 第二个数字
        
    Returns:
        两个数字的和
    """
    return a + b
