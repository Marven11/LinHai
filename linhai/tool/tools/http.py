from linhai.tool.base import register_tool
import requests
from typing import Optional


@register_tool(
    name="http_request",
    desc="使用requests库发送HTTP请求并获取响应内容",
    args={
        "method": {"desc": "HTTP方法，如GET、POST", "type": "str"},
        "url": {"desc": "请求的URL", "type": "str"},
        "params": {"desc": "查询参数（字典形式）", "type": "Optional[dict]"},
        "headers": {"desc": "请求头（字典形式）", "type": "Optional[dict]"},
        "data": {"desc": "请求体数据", "type": "Optional[str]"},
    },
    required_args=["method", "url"],
)
def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
) -> str:
    """
    发送HTTP请求并返回响应内容
    """
    try:
        response = requests.request(
            method=method, url=url, params=params, headers=headers, data=data
        )
        return response.text
    except Exception as e:
        return f"请求失败: {str(e)}"
