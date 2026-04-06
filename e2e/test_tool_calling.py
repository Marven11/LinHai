import json

import pytest
from openai import AsyncOpenAI

from linhai.llm import ToolCallMessage
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.tool.base import ToolArgInfo, ToolSet, to_tools_info

pytestmark = pytest.mark.asyncio

SYSTEM_PROMPT = """You are a helpful assistant that uses tools when requested.

## Tool Calling Format

When you need to call a tool, output a JSON code block with the language tag `json toolcall`:

```json toolcall
{"name": "tool_name", "arguments": {"param": "value"}}
```

## Available Tools

{tools_json}

When the user asks about weather, call the get_weather tool with the city name.
"""


def _get_weather_toolset() -> ToolSet:
    toolset = ToolSet()

    @toolset.register_tool(
        name="get_weather",
        desc="Get the current weather for a given city",
        args={"city": ToolArgInfo(desc="The city name", type="string")},
        required_args=["city"],
    )
    def get_weather(city: str):
        return f"Sunny, 25°C in {city}"

    return toolset


def _build_system_prompt() -> str:
    toolset = _get_weather_toolset()
    tools_json = json.dumps(to_tools_info(toolset.get_tools()), ensure_ascii=False)
    return SYSTEM_PROMPT.format(tools_json=tools_json)


async def _get_tool_call_response(client: AsyncOpenAI, max_retries: int = 3) -> str:
    system_prompt = _build_system_prompt()
    for _ in range(max_retries):
        response = await client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is the weather in Tokyo?"},
            ],
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        tool_calls, _ = extract_tool_calls_with_errors(content)
        if tool_calls:
            return content
    pytest.fail("Free model did not generate json toolcall blocks after retries")


async def test_llm_generates_tool_call(openrouter_client: AsyncOpenAI):
    content = await _get_tool_call_response(openrouter_client)
    tool_calls, errors = extract_tool_calls_with_errors(content)
    assert not errors, f"Tool call parse errors: {errors}"
    assert len(tool_calls) == 1
    call = tool_calls[0]
    assert call["name"] == "get_weather"
    assert "city" in call["arguments"]
    assert (
        "Tokyo" in call["arguments"]["city"]
        or "tokyo" in call["arguments"]["city"].lower()
    )


async def test_tool_result_processing(openrouter_client: AsyncOpenAI):
    content = await _get_tool_call_response(openrouter_client)
    tool_calls, _ = extract_tool_calls_with_errors(content)
    assert tool_calls

    tool_result = (
        "<<tool>>\n"
        "<<name>>get_weather<<name>>\n"
        "<<index>>1<<index>>\n"
        "<<message>>\u5de5\u5177\u6267\u884c\u6210\u529f<<message>>\n"
        "<<data>>Sunny, 25\u00b0C in Tokyo<<data>>\n"
        "<<tool>>"
    )

    system_prompt = _build_system_prompt()
    response2 = await openrouter_client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "What is the weather in Tokyo?"},
            {"role": "assistant", "content": content},
            {"role": "user", "content": tool_result},
        ],
        max_tokens=200,
    )
    final = response2.choices[0].message.content or ""
    assert len(final) > 0


def test_tool_call_message_assert_success():
    msg = ToolCallMessage(
        function_name="get_weather",
        function_arguments={"city": "Tokyo"},
        assert_success=True,
        with_secret=None,
    )
    assert msg.assert_success is True
    assert msg.function_name == "get_weather"
    assert msg.function_arguments == {"city": "Tokyo"}

    msg_false = ToolCallMessage(
        function_name="read_file",
        function_arguments={"filepath": "/tmp/test"},
        assert_success=False,
        with_secret=["SECRET_KEY"],
    )
    assert msg_false.assert_success is False
    assert msg_false.function_name == "read_file"
    assert msg_false.with_secret == ["SECRET_KEY"]
