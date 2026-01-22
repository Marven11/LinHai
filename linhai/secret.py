"""Secret management module for LinHai agent."""

import re
from typing import Any, TypedDict
import tomllib
from pathlib import Path

from .exceptions import ConfigValidationError
from .llm import ToolCallMessage
from .agent.base import RuntimeMessage
from .agent import Agent


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
    """在工具调用前替换参数中的secret键，确保工具能访问敏感信息。"""
    replace_map = filter_secrets_by_keys(secrets_dict, secret_keys)
    return recursive_string_replace(obj, replace_map)


def mask_secrets_in_object(
    obj: Any, secrets_dict: dict[str, SecretInfo], with_secret: list[str]
) -> Any:
    """在工具返回结果后掩码secret值，保护敏感信息不泄露。"""
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


class SecretInterceptorPlugin:
    def __init__(self, group_chat, secrets_dict: dict[str, SecretInfo]):
        self.group_chat = group_chat
        self.secrets_dict = secrets_dict

    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        with_secret = tool_call.with_secret
        if not with_secret:
            return False

        missing_keys = [key for key in with_secret if key not in self.secrets_dict]

        if missing_keys:
            agent = self.group_chat.get_members("agent", Agent)
            error_msg = f"以下secret键未找到: {missing_keys}。请检查secret配置文件。"
            agent.message_processor.add_new_message(RuntimeMessage(error_msg))
            return True

        tool_call.function_arguments = replace_secrets_in_object(
            tool_call.function_arguments, self.secrets_dict, with_secret
        )
        return False

    async def after_tool_call(self, _agent, tool_call, tool_result, _success) -> Any:

        with_secret = tool_call.with_secret
        msg = tool_result

        if with_secret:
            llm_tool_result = tool_result.to_llm_message()
            masked_result = mask_secrets_in_object(
                llm_tool_result["content"], self.secrets_dict, with_secret
            )

            keys_str = ", ".join(with_secret)
            message = f"<<masked>><<message>>工具内容包含{keys_str}secret的内容，已替换<<message>><<content>>{masked_result}<<content>><<masked>>"
            msg = RuntimeMessage(message)

        result_str = str(msg)
        contains_secrets = []
        for key, secret_info in self.secrets_dict.items():
            if secret_info["value"] in result_str:
                contains_secrets.append(key)

        if contains_secrets:
            message = (
                f"工具调用的结果包含secret值{contains_secrets}，已拦截。"
                "如果需要查看内容则需要使用with_secret指定对应的键，其中的secret值会被secret键拦截"
            )
            return RuntimeMessage(message)

        return None if msg is tool_result else msg

    def register(self, lifecycle):
        lifecycle.register_before_tool_call(self.before_tool_call)
        lifecycle.register_after_tool_call(self.after_tool_call)


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
