"""Secret management module for LinHai agent."""

import re
from typing import Any, TypedDict, Literal, Union
import tomllib
from pathlib import Path

from .exceptions import ConfigValidationError
from .agent.base import RuntimeMessage
from .agent.conversation import get_current_conversation
import time


class SecretInfo(TypedDict):
    value: str
    description: str


def load_secrets_from_config(
    config_path: str, base_dir: str | Path
) -> dict[str, SecretInfo]:
    # 如果config_path为空或非字符串，后续操作会自然失败
    config_path = config_path.strip()
    # 只对config_path进行expanduser处理，base_dir由调用者处理
    path = Path(config_path).expanduser()

    # base_dir直接转换为Path对象，不处理expanduser
    base_dir = Path(base_dir)

    if not path.is_absolute():
        path = base_dir / path

    if not path.exists():
        raise FileNotFoundError(f"Secret config file not found: {path}")

    with path.open("rb") as f:
        config_data = tomllib.load(f)

    if "secrets" not in config_data:
        raise ConfigValidationError("Secret config must contain 'secrets' section")

    secrets_section = config_data["secrets"]
    result: dict[str, SecretInfo] = {}

    for key, value in secrets_section.items():
        if not isinstance(value, dict):
            raise ConfigValidationError(
                f"Secret '{key}' must be a dictionary with 'value' and 'description' fields"
            )
        if "value" not in value:
            raise ConfigValidationError(f"Secret '{key}' missing 'value' field")
        if "description" not in value:
            raise ConfigValidationError(f"Secret '{key}' missing 'description' field")

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", key):
            raise ConfigValidationError(
                f"Secret key '{key}' must contain only letters, numbers, hyphens, and underscores, "
                "and must not start with a digit"
            )

        result[key] = SecretInfo(
            value=str(value["value"]),
            description=str(value["description"]),
        )

    return result


def filter_secrets_by_keys(
    secrets_dict: dict[str, SecretInfo], secret_keys: list[str]
) -> dict[str, str]:
    """根据with_secret列表过滤secret字典，生成替换映射用于后续替换。"""
    replace_map: dict[str, str] = {}
    for key in secret_keys:
        if key in secrets_dict:
            secret_value = secrets_dict[key]["value"]
            replace_map[f"<${key}$>"] = secret_value
    return replace_map


def recursive_string_replace(obj: object, replace_map: dict[str, str]) -> object:
    """递归替换字符串、字典或列表中的模式，用于secret值的替换和掩码。"""
    if isinstance(obj, str):
        result = obj
        for pattern, replacement in replace_map.items():
            result = result.replace(pattern, replacement)
        return result

    elif isinstance(obj, dict):
        return {k: recursive_string_replace(v, replace_map) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [recursive_string_replace(item, replace_map) for item in obj]

    else:
        return obj


def replace_secrets_in_object(
    obj: Any, secrets_dict: dict[str, SecretInfo], secret_keys: list[str]
) -> Any:
    replace_map = filter_secrets_by_keys(secrets_dict, secret_keys)
    return recursive_string_replace(obj, replace_map)


def mask_secrets_in_object(
    obj: Any, secrets_dict: dict[str, SecretInfo], with_secret: list[str]
) -> Any:
    replace_map: dict[str, str] = {}
    for key in with_secret:
        if key in secrets_dict:
            secret_value = secrets_dict[key]["value"]
            replace_map[secret_value] = f"<${key}$>"

    sorted_replace_map = dict(
        sorted(replace_map.items(), key=lambda x: len(x[0]), reverse=True)
    )

    return recursive_string_replace(obj, sorted_replace_map)


def get_available_secrets_message(secrets_dict: dict[str, SecretInfo]) -> str:
    if not secrets_dict:
        return "无可用secret键"

    items = []
    for key, secret_info in secrets_dict.items():
        description = secret_info["description"]
        items.append(f"<${key}$> - {description}")

    return "当前可用secret键: " + "; ".join(items)


def contains_any_secret(obj: Any, secrets_dict: dict[str, SecretInfo]) -> bool:
    secret_values = {secret_info["value"] for secret_info in secrets_dict.values()}
    
    if isinstance(obj, str):
        for secret_value in secret_values:
            if secret_value in obj:
                return True
        return False

    elif isinstance(obj, dict):
        for value in obj.values():
            if contains_any_secret(value, secrets_dict):
                return True
        return False

    elif isinstance(obj, list):
        for item in obj:
            if contains_any_secret(item, secrets_dict):
                return True
        return False

    else:
        return False


class SecretInterceptorPlugin:
    def __init__(self, group_chat, secrets_dict: dict[str, SecretInfo]):
        self.group_chat = group_chat
        self.secrets_dict = secrets_dict

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        result_content: str | None,
        toolcall_arguments: dict | None,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        _ = (tool_index, toolcall_arguments, is_tool_failed_duplicated_error)
        if status == "skipped":
            return None

        elif status in ["success", "failed"]:
            if result_content is None:
                return None

            if with_secret:
                result_content = mask_secrets_in_object(
                    result_content, self.secrets_dict, with_secret
                )

            if contains_any_secret(result_content, self.secrets_dict):
                conversation = get_current_conversation()
                timestamp = int(time.time())
                filename = f"secret_intercepted_{timestamp}_{tool_name}.txt"
                filepath = conversation.conversation_dir / filename
                filepath.write_text(str(result_content), encoding="utf-8")

                message = (
                    f"工具调用的结果包含未指定的secret值，已拦截。"
                    f"原始内容已保存到文件: {filepath}"
                )
                return RuntimeMessage(message)

            if with_secret:
                message = f"<<masked>><<message>>工具内容包含{with_secret!r}secret的内容，已替换<<message>><<content>>{result_content}<<content>><<masked>>"
                return RuntimeMessage(message)

            return None

        return None

    def register(self, lifecycle):
        lifecycle.register_on_tool_result(self.on_tool_result)


def initialize_secret_system(
    group_chat, secret_config_path: str, config_basedir: str | Path
):
    from linhai.llm import SystemMessage
    from linhai.prompt import INTRODUCTION_SECRET_SYSTEM

    if not secret_config_path:
        raise ValueError("Secret config path is empty")
    if not isinstance(secret_config_path, str):
        raise ValueError(
            f"Secret config path must be string, got {type(secret_config_path).__name__}: {secret_config_path!r}"
        )

    config_path = secret_config_path.strip()
    if not config_path:
        raise ValueError("Secret config path is empty after stripping whitespace")

    secrets_dict = load_secrets_from_config(config_path, config_basedir)

    secret_plugin = SecretInterceptorPlugin(group_chat, secrets_dict)

    secrets_message = get_available_secrets_message(secrets_dict)
    if secrets_message:

        def add_secret_rule():
            system_message = group_chat.get_members("system_message", SystemMessage)
            rule_content = INTRODUCTION_SECRET_SYSTEM.format(
                secrets_list=secrets_message
            )
            system_message.add_rule("SECRET SYSTEM", rule_content)

        group_chat.add_postinit(add_secret_rule)

    # 添加postinit回调来注册插件到lifecycle
    def register_plugin_to_lifecycle():
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = group_chat.get_members("lifecycle", Lifecycle)
        secret_plugin.register(lifecycle)

    group_chat.add_postinit(register_plugin_to_lifecycle)

    return secret_plugin
