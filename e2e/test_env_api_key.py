import os
import tempfile
import uuid

import pytest

from linhai.base import SystemMessage, UserMessage
from linhai.config import load_config
from linhai.llm import OpenAi
from linhai.registry import Registry

from conftest import retry_llm_call

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1"
DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash"


def _create_llm_from_env_config(tmp_dir: str) -> tuple[OpenAi, Registry, str]:
    random_uuid = str(uuid.uuid4())
    config_path = os.path.join(tmp_dir, "config.toml")
    with open(config_path, "w") as f:
        f.write(
            f'[[llm]]\nname = "deepseek"\n'
            f'base_url = "{DEEPSEEK_BASE_URL}"\n'
            f'api_key = {{type = "env", name = "DEEPSEEK_API_KEY"}}\n'
            f'model = "{DEEPSEEK_MODEL}"\n'
        )
    os.environ["DEEPSEEK_API_KEY"] = "gomodel-master-key"
    config = load_config(config_path)
    assert config.llm[0].api_key == "gomodel-master-key"

    registry = Registry()
    registry.register_queue("token_usage")
    llm = OpenAi(
        registry=registry,
        api_key=config.llm[0].api_key,
        base_url=config.llm[0].base_url,
        model=config.llm[0].model,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={
            "max_tokens": 200,
            "stream_options": {"include_usage": True},
        },
        support_image=False,
        explicit_cache_info=None,
        name="deepseek",
    )
    return llm, registry, random_uuid


async def test_env_api_key_llm_connection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        llm, registry, random_uuid = _create_llm_from_env_config(tmp_dir)
        system_msg = SystemMessage(registry)

        async def try_once():
            answer = await llm.answer_stream(
                [system_msg, UserMessage(f"Repeat this uuid: {random_uuid}")]
            )
            tokens: list = []
            async for t in answer:
                tokens.append(t)
            content = answer.get_current_content()
            return content if random_uuid in content else None

        await retry_llm_call(try_once)
