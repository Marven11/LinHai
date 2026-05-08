import json

import pytest
from openai import AsyncOpenAI

from linhai.base import SystemMessage
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.registry import Registry
from linhai.secret import (
    SecretInfo,
    get_available_secrets_message,
    _CALL_WITH_SECRET_RULE,
)
from linhai.tool.base import ToolArgInfo, ToolSet, to_tools_info

from conftest import retry_llm_call

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1/deepseek"
DEEPSEEK_MODEL = "deepseek-reasoner"


def _make_write_file_toolset() -> ToolSet:
    toolset = ToolSet()

    @toolset.register_tool(
        name="write_file",
        desc="Write content to a file",
        args={
            "filepath": ToolArgInfo(desc="File path", type="str"),
            "content": ToolArgInfo(desc="File content", type="str"),
        },
        required_args=["filepath", "content"],
    )
    def write_file(filepath: str, content: str):
        return f"Written to {filepath}"

    return toolset


def _make_call_with_secret_toolset() -> ToolSet:
    toolset = ToolSet()

    @toolset.register_tool(
        name="call_with_secret",
        desc=(
            "使用secret调用另一个工具。"
            "将目标工具的名字、参数和with_secret列表传入，"
            "本工具会替换参数中的占位符为secret值，"
            "然后调用目标工具并返回掩码后的结果。"
        ),
        args={
            "tool_name": ToolArgInfo(desc="要调用的目标工具名称", type="str"),
            "tool_arguments": ToolArgInfo(
                desc="目标工具的参数字典，其中可以包含占位符引用secret值",
                type="dict",
            ),
            "with_secret": ToolArgInfo(
                desc="with_secret字典，包含in_arguments和in_result两个列表",
                type="dict",
            ),
        },
        required_args=["tool_name", "tool_arguments", "with_secret"],
    )
    def call_with_secret(tool_name: str, tool_arguments: dict, with_secret: dict):
        return f"Called {tool_name} with secrets"

    return toolset


def _build_system_prompt_with_secrets() -> str:
    registry = Registry()
    system_message = SystemMessage(registry)

    for title in [
        "SOUL",
        "WAITING USER AND AUTO RUN",
        "GLOBAL PROMPT",
        "CONTEXT MANAGEMENT",
        "MACHINE CONTROL BASIC",
    ]:
        system_message.remove_introduction(title)
    for title in ["CODING STYLE", "USER INTERACTION"]:
        system_message.remove_rule(title)
    system_message.remove_example("SECRET")

    secrets_dict = {
        "DEEPSEEK_API_KEY": SecretInfo(
            value="test-deepseek-key-12345",
            description="DeepSeek API key",
            disabled_in_toolcall_argument=False,
        ),
    }
    secrets_message = get_available_secrets_message(secrets_dict)
    rule_content = _CALL_WITH_SECRET_RULE.format(secrets_list=secrets_message)
    system_message.add_rule("CALL WITH SECRET", rule_content)

    write_toolset = _make_write_file_toolset()
    secret_toolset = _make_call_with_secret_toolset()
    all_tools = {**write_toolset.get_tools(), **secret_toolset.get_tools()}
    tools_json = json.dumps(to_tools_info(all_tools), ensure_ascii=False)
    system_message.add_introduction("TOOLS", tools_json)

    return system_message.get_content()


async def _get_secret_tool_call_response(client: AsyncOpenAI) -> str:
    system_prompt = _build_system_prompt_with_secrets()

    async def try_once():
        response = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "请用call_with_secret工具调用write_file，"
                        "将一个包含DEEPSEEK_API_KEY的Python代码示例"
                        "写入/tmp/api_example.py文件。"
                        "代码中应该包含: openai API调用使用DEEPSEEK_API_KEY作为api_key。"
                        "记得在with_secret中包含DEEPSEEK_API_KEY。"
                    ),
                },
            ],
            max_tokens=500,
        )
        content = response.choices[0].message.content or ""
        tool_calls, _ = extract_tool_calls_with_errors(content)
        return content if tool_calls else None

    return await retry_llm_call(try_once)


async def test_llm_generates_call_with_secret(llm_client: AsyncOpenAI):
    content = await _get_secret_tool_call_response(llm_client)
    tool_calls, errors = extract_tool_calls_with_errors(content)
    assert not errors, f"Tool call parse errors: {errors}"
    assert len(tool_calls) >= 1

    call = tool_calls[0]
    assert call["name"] == "call_with_secret"
    args = call["arguments"]
    assert args["tool_name"] == "write_file"
    assert "DEEPSEEK_API_KEY" in str(args.get("with_secret", {}))


async def test_with_secret_format_has_in_arguments_and_in_result(
    llm_client: AsyncOpenAI,
):
    content = await _get_secret_tool_call_response(llm_client)
    tool_calls, _ = extract_tool_calls_with_errors(content)
    call = tool_calls[0]
    args = call["arguments"]
    with_secret = args.get("with_secret")

    if isinstance(with_secret, dict):
        assert "in_arguments" in with_secret or "in_result" in with_secret
        if "in_arguments" in with_secret:
            assert "DEEPSEEK_API_KEY" in with_secret["in_arguments"]
    elif isinstance(with_secret, list):
        assert "DEEPSEEK_API_KEY" in with_secret


async def test_secret_placeholder_in_tool_arguments(llm_client: AsyncOpenAI):
    content = await _get_secret_tool_call_response(llm_client)
    tool_calls, _ = extract_tool_calls_with_errors(content)
    call = tool_calls[0]
    args = call["arguments"]
    tool_arguments = args.get("tool_arguments", {})
    content_str = json.dumps(tool_arguments, ensure_ascii=False)
    assert "<$DEEPSEEK_API_KEY$>" in content_str
