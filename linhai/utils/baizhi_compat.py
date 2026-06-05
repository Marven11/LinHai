"""百智云兼容性辅助函数。

百智云(baizhi.cloud)在处理包含无效JSON的tool call arguments时
会返回502错误，提示请求解码失败。

这些函数在将消息发送给百智云API之前，
检查assistant消息中每个tool call的function.arguments是否为合法JSON。
对于无效JSON，将其替换为包含原始无效JSON字符串的dummy arguments，
以绕过百智云的502错误。
"""

from __future__ import annotations

import json
import asyncio
from typing import Any, Sequence

from linhai.type_hints import LanguageModelMessage


async def _try_parse_json(json_str: str) -> dict[str, Any]:
    return json.loads(json_str)


async def _is_valid_json(json_str: str) -> bool:
    results = await asyncio.gather(_try_parse_json(json_str), return_exceptions=True)
    return not isinstance(results[0], BaseException)


def _build_dummy_arguments(original_args: str) -> str:
    return json.dumps(
        {
            "notice": "This Toolcall is invalid, causing baizhi.cloud responding 502. Original arguments is provided as a string.",
            "original_arguments": original_args,
        },
        ensure_ascii=False,
    )


async def fix_baizhi_messages(
    messages: Sequence[LanguageModelMessage],
) -> Sequence[LanguageModelMessage]:
    """修复消息列表中的无效tool call arguments以兼容百智云。

    百智云(baizhi.cloud)在处理包含无效JSON的tool call arguments时
    会返回502错误。此函数遍历每条assistant消息的tool_calls，
    检查function.arguments是否为合法JSON。对于无效JSON，
    将其替换为包含原始无效JSON字符串的dummy arguments，
    以保留原始信息的同时绕过百智云的502错误。

    Args:
        messages: 已通过to_llm_message()转换的消息列表

    Returns:
        修复后的消息列表，assistant消息中无效的tool call arguments
        已被替换为dummy JSON
    """
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            continue
        for tc in tool_calls:
            function = tc.get("function")
            if not function:
                continue
            args = function.get("arguments", "")
            if not args:
                continue
            if not await _is_valid_json(args):
                function["arguments"] = _build_dummy_arguments(args)
    return messages
