import json

import pytest
from openai import AsyncOpenAI

from linhai.base import SystemMessage, ToolCallMessage
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.registry import Registry
from linhai.tool.base import ToolArgInfo, ToolSet, to_tools_info

from conftest import retry_llm_call


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
    registry = Registry()
    system_message = SystemMessage(registry)
    for title in [
        "SOUL",
        "WAITING USER AND AUTO RUN",
        "GLOBAL PROMPT",
        "CONTEXT MANAGEMENT",
        "SECRET SYSTEM",
        "MACHINE CONTROL BASIC",
    ]:
        system_message.remove_introduction(title)
    for title in ["CODING STYLE", "USER INTERACTION"]:
        system_message.remove_rule(title)
    system_message.remove_example("SECRET")
    toolset = _get_weather_toolset()
    tools_json = json.dumps(to_tools_info(toolset.get_tools()), ensure_ascii=False)
    system_message.add_introduction("TOOLS", tools_json)
    return system_message.get_content()


async def _get_tool_call_response(client: AsyncOpenAI) -> str:
    system_prompt = _build_system_prompt()

    async def try_once():
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is the weather in Tokyo?"},
            ],
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        tool_calls, _ = extract_tool_calls_with_errors(content)
        return content if tool_calls else None

    return await retry_llm_call(try_once)


async def test_llm_generates_tool_call(llm_client: AsyncOpenAI):
    content = await _get_tool_call_response(llm_client)
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


async def test_tool_result_processing(llm_client: AsyncOpenAI):
    content = await _get_tool_call_response(llm_client)
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

    async def try_once():
        response2 = await llm_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is the weather in Tokyo?"},
                {"role": "assistant", "content": content},
                {"role": "user", "content": tool_result},
            ],
            max_tokens=200,
        )
        final = response2.choices[0].message.content or ""
        return final if final else None

    await retry_llm_call(try_once)


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
