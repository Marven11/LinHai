"""Secret management module for LinHai agent."""

import re
from typing import Any, TypedDict, Literal, Union, TypeVar, TYPE_CHECKING, overload

import tomllib
from pathlib import Path

from .exceptions import ConfigValidationError
from .agent.messages import RuntimeMessage
from .agent.conversation import save_secret_intercepted
from .base import Message
from .agent.lifecycle import Lifecycle
from .tool.base import SuccessfulToolResult, FailedToolResult

if TYPE_CHECKING:
    from .registry import Registry


class SecretInfo(TypedDict):
    value: str
    description: str
    disabled_in_toolcall_argument: bool


def load_secrets_from_config(
    config_path: str, base_dir: str | Path | None
) -> dict[str, SecretInfo]:
    if base_dir is None:
        raise ValueError("Secret配置需要config_basedir")
    config_path = config_path.strip()
    path = Path(config_path).expanduser()

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

        disabled = value.get("disabled_in_toolcall_argument", False)
        if not isinstance(disabled, bool):
            raise ConfigValidationError(
                f"Secret '{key}' field 'disabled_in_toolcall_argument' must be boolean"
            )
        result[key] = SecretInfo(
            value=str(value["value"]),
            description=str(value["description"]),
            disabled_in_toolcall_argument=disabled,
        )

    return result


def filter_secrets_by_keys(
    secrets_dict: dict[str, SecretInfo], secret_keys: list[str]
) -> dict[str, str]:
    """根据with_secret列表过滤secret字典，生成替换映射用于后续替换。"""
    replace_map: dict[str, str] = {}
    for key in secret_keys:
        if key in secrets_dict:
            secret_info = secrets_dict[key]
            if secret_info["disabled_in_toolcall_argument"]:
                continue
            secret_value = secret_info["value"]
            replace_map[f"<${key}$>"] = secret_value
    return replace_map


T = TypeVar("T")


@overload
def recursive_string_replace(obj: str, replace_map: dict[str, str]) -> str: ...


@overload
def recursive_string_replace(obj: T, replace_map: dict[str, str]) -> T: ...


def recursive_string_replace(obj: T, replace_map: dict[str, str]) -> Any:
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
    obj: T, secrets_dict: dict[str, SecretInfo], secret_keys: list[str]
) -> T:
    replace_map = filter_secrets_by_keys(secrets_dict, secret_keys)
    return recursive_string_replace(obj, replace_map)


def mask_secrets_in_object(
    obj: T, secrets_dict: dict[str, SecretInfo], with_secret: list[str]
) -> T:
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
        disabled = secret_info["disabled_in_toolcall_argument"]
        items.append(
            f"<${key}$> - {description} (disabled_in_toolcall_argument={disabled})"
        )

    return "当前可用secret键: " + "; ".join(items)


def find_matching_secret_keys(obj: T, secrets_dict: dict[str, SecretInfo]) -> list[str]:
    if isinstance(obj, str):
        return [
            key
            for key, secret_info in secrets_dict.items()
            if secret_info["value"] in obj
        ]

    elif isinstance(obj, dict):
        keys: list[str] = []
        for value in obj.values():
            keys.extend(find_matching_secret_keys(value, secrets_dict))
        return list(dict.fromkeys(keys))

    elif isinstance(obj, list):
        keys_list: list[str] = []
        for item in obj:
            keys_list.extend(find_matching_secret_keys(item, secrets_dict))
        return list(dict.fromkeys(keys_list))

    return []


def contains_any_secret(obj: T, secrets_dict: dict[str, SecretInfo]) -> bool:
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
    def __init__(self, registry: "Registry", secrets_dict: dict[str, SecretInfo]):
        self.registry = registry
        self.secrets_dict = secrets_dict

    async def after_toolcall(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        _ = (tool_index, toolcall_arguments, is_tool_failed_duplicated_error)
        if status == "skipped":
            return None

        elif status in ["success", "failed"]:
            if message is None:
                return None

            result_content = message.get_content()
            if result_content is None:
                return None

            if with_secret:
                result_content = mask_secrets_in_object(
                    result_content, self.secrets_dict, with_secret
                )

            matched_keys = find_matching_secret_keys(result_content, self.secrets_dict)
            if matched_keys:
                conversation_dir = self.registry.get_member_typechecked(
                    "conversation_folder", Path
                )
                filepath = save_secret_intercepted(
                    conversation_dir, str(result_content), tool_name
                )

                keys_str = ", ".join(matched_keys)
                return_message = (
                    f"工具结果中包含以下secret键的内容: {keys_str}。"
                    f"请将以上secret键添加到with_secret字段中以查看掩码后的结果。"
                    f"原始内容已保存到文件: {filepath}"
                )
                return RuntimeMessage(return_message)

            if with_secret:
                return_message = f"<<masked>><<message>>工具内容包含{with_secret!r}secret的内容，已替换<<message>><<content>>{result_content}<<content>><<masked>>"
                return RuntimeMessage(return_message)

            return None

        return None

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: list[str] | None,
    ) -> Union[SuccessfulToolResult, FailedToolResult, dict, None]:
        _ = tool_name  # unused parameter
        if with_secret is None:
            return None

        cleaned_keys: list[str] = []
        for key in with_secret:
            cleaned_key = key
            if key.startswith("<$") and key.endswith("$>"):
                return FailedToolResult(
                    content=f"在{tool_name}工具调用中：Secret键 '{key}' 未找到，请使用 'KEY' 而不是 '<$KEY$>' 格式"
                )
            cleaned_keys.append(cleaned_key)
            if cleaned_key not in self.secrets_dict:
                return FailedToolResult(
                    content=f"在{tool_name}工具调用中：Secret键 '{key}' 未找到"
                )
            secret_info = self.secrets_dict[cleaned_key]
            if secret_info["disabled_in_toolcall_argument"]:
                return FailedToolResult(
                    content=f"在{tool_name}工具调用中：Secret键 '{key}' 被禁止在工具调用参数中使用"
                )

        return replace_secrets_in_object(
            toolcall_arguments, self.secrets_dict, cleaned_keys
        )

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.after_toolcall.register(self.after_toolcall)
        lifecycle.before_tool_call.register(self.before_tool_call)


def initialize_secret_system(
    registry: "Registry", secret_config_path: str, config_basedir: str | Path | None
) -> SecretInterceptorPlugin:
    from linhai.base import SystemMessage
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

    secret_plugin = SecretInterceptorPlugin(registry, secrets_dict)

    secrets_message = get_available_secrets_message(secrets_dict)
    if secrets_message:

        def add_secret_rule():
            system_message = registry.get_member_typechecked(
                "system_message", SystemMessage
            )
            rule_content = INTRODUCTION_SECRET_SYSTEM.format(
                secrets_list=secrets_message
            )
            system_message.add_rule("SECRET SYSTEM", rule_content)

        registry.add_postinit(add_secret_rule)

    def register_plugin_to_lifecycle():
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        secret_plugin.register(lifecycle)

    registry.add_postinit(register_plugin_to_lifecycle)

    return secret_plugin
