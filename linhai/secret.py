"""Secret management module for LinHai agent."""

import re
from typing import Any, TypedDict, Literal, Union, TypeVar, TYPE_CHECKING, overload

import tomllib
from pathlib import Path

from .exceptions import ConfigValidationError
from .agent.messages import RuntimeMessage
from .agent.conversation import save_secret_intercepted
from .base import Message
from .agent.lifecycle import AfterToolcallResult, Lifecycle
from .type_hints import WithSecret
from .tool.base import SuccessfulToolResult, FailedToolResult, ToolSet, ToolArgInfo

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
    obj: T, secrets_dict: dict[str, SecretInfo], in_arguments: list[str]
) -> T:
    replace_map = filter_secrets_by_keys(secrets_dict, in_arguments)
    return recursive_string_replace(obj, replace_map)


def mask_secrets_in_object(
    obj: T, secrets_dict: dict[str, SecretInfo], in_result: list[str]
) -> T:
    replace_map: dict[str, str] = {}
    for key in in_result:
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


def _create_call_with_secret_toolset(
    secrets_dict: dict[str, SecretInfo], registry: "Registry"
) -> ToolSet:
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
            "tool_name": ToolArgInfo(
                desc="要调用的目标工具名称",
                type="str",
            ),
            "tool_arguments": ToolArgInfo(
                desc="目标工具的参数字典，其中可以包含占位符引用secret值",
                type="dict",
            ),
            "with_secret": ToolArgInfo(
                desc="secret配置字典，包含in_arguments(参数替换)和in_result(结果掩码)两个列表",
                type="dict",
            ),
        },
        required_args=["tool_name", "tool_arguments", "with_secret"],
    )
    async def call_with_secret(tool_name: str, tool_arguments: dict, with_secret: dict):
        in_arguments: list[str] = with_secret.get("in_arguments", [])
        in_result_keys: list[str] = with_secret.get("in_result", [])

        cleaned_arg_keys: list[str] = []
        for key in in_arguments:
            if key.startswith("<$") and key.endswith("$>"):
                return FailedToolResult(
                    content=(
                        f"Secret键 '{key}' 格式错误，" f"请使用 'KEY' 而不是占位符格式"
                    )
                )
            if key not in secrets_dict:
                return FailedToolResult(content=f"Secret键 '{key}' 未找到")
            secret_info = secrets_dict[key]
            if secret_info["disabled_in_toolcall_argument"]:
                return FailedToolResult(
                    content=f"Secret键 '{key}' 被禁止在工具调用参数中使用"
                )
            cleaned_arg_keys.append(key)

        replaced_args = replace_secrets_in_object(
            tool_arguments, secrets_dict, cleaned_arg_keys
        )

        from linhai.base import ToolCallMessage
        from linhai.tool.main import ToolManager

        tool_manager = registry.get_member_typechecked("tool_manager", ToolManager)
        tool_call = ToolCallMessage(
            function_name=tool_name,
            function_arguments=replaced_args,
            assert_success=True,
            with_secret=None,
        )
        result_msg = await tool_manager.process_tool_call(tool_call, 0)

        result_content = result_msg.get_content()
        if result_content is None:
            return SuccessfulToolResult(content="工具执行完成，无文本输出")

        matched_keys = find_matching_secret_keys(result_content, secrets_dict)
        if matched_keys:
            conversation_dir = registry.get_member_typechecked(
                "conversation_folder", Path
            )
            filepath = save_secret_intercepted(
                conversation_dir, str(result_content), tool_name
            )
            keys_str = ", ".join(matched_keys)
            return SuccessfulToolResult(
                content=(
                    f"工具结果中包含以下secret键的内容: {keys_str}。"
                    f"原始内容已保存到文件: {filepath}"
                )
            )

        masked_content = mask_secrets_in_object(
            result_content, secrets_dict, in_result_keys
        )
        return SuccessfulToolResult(content=masked_content)

    return toolset


_CALL_WITH_SECRET_RULE = """\
## call_with_secret工具

当你使用的LLM不支持自定义工具调用格式时，使用call_with_secret工具代替：

1. 将目标工具名放入tool_name参数
2. 将目标工具的参数放入tool_arguments参数，secret值用占位符
3. 将secret配置放入with_secret参数，格式为 {{"in_arguments": [...], "in_result": [...]}}

示例：调用write_file工具并使用SECRET_PASSWORD

tool_name: write_file
tool_arguments: filepath和content等参数，其中secret用占位符
with_secret: {{"in_arguments": ["SECRET_PASSWORD"], "in_result": ["SECRET_PASSWORD"]}}

可用secret键: {secrets_list}"""


class SecretToolsetPlugin:
    def __init__(
        self,
        registry: "Registry",
        secrets_dict: dict[str, SecretInfo],
    ):
        self.registry = registry
        self.secrets_dict = secrets_dict

    async def before_message_generation(self) -> None:
        from linhai.agent.main import Agent
        from linhai.base import SystemMessage
        from linhai.tool.main import ToolManager

        agent = self.registry.get_member_typechecked("agent", Agent)
        tool_manager = self.registry.get_member_typechecked("tool_manager", ToolManager)
        system_message = self.registry.get_member_typechecked(
            "system_message", SystemMessage
        )

        current_llm = agent.get_current_model()
        use_custom = current_llm.get_custom_toolcall_format()

        if use_custom:
            tool_manager.set_toolset_enabled("secret_wrapper", False)
            system_message.remove_rule("CALL WITH SECRET")
        else:
            tool_manager.set_toolset_enabled("secret_wrapper", True)
            secrets_message = get_available_secrets_message(self.secrets_dict)
            rule_content = _CALL_WITH_SECRET_RULE.format(secrets_list=secrets_message)
            system_message.remove_rule("CALL WITH SECRET")
            system_message.add_rule("CALL WITH SECRET", rule_content)

    def register(self, lifecycle: "Lifecycle"):
        lifecycle.before_message_generation.register(self.before_message_generation)


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
        with_secret: WithSecret | None,
        is_tool_failed_duplicated_error: bool,
    ) -> AfterToolcallResult | None:
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
                    result_content, self.secrets_dict, with_secret["in_result"]
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
                    f"原始内容已保存到文件: {filepath}"
                    f"你可以: 1. 带上合适的secret键重新调用工具 2. 带上合适的secret键查看原始内容文件"
                )
                return AfterToolcallResult(replacement=RuntimeMessage(return_message))

            if with_secret:
                return_message = f"<<masked>><<message>>工具内容包含{with_secret['in_result']!r}secret的内容，已替换<<message>><<content>>{result_content}<<content>><<masked>>"
                return AfterToolcallResult(replacement=RuntimeMessage(return_message))

            return None

        return None

    async def before_tool_call(
        self,
        tool_name: str,
        toolcall_arguments: dict,
        with_secret: WithSecret | None,
    ) -> Union[SuccessfulToolResult, FailedToolResult, dict, None]:
        _ = tool_name  # unused parameter
        if with_secret is None:
            return None

        cleaned_keys: list[str] = []
        for key in with_secret["in_arguments"]:
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
            system_message.add_introduction("SECRET SYSTEM", rule_content)

        registry.add_postinit(add_secret_rule)

    def register_plugin_to_lifecycle():
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        secret_plugin.register(lifecycle)

    def register_secret_toolset():
        from linhai.tool.main import ToolManager

        tool_manager = registry.get_member_typechecked("tool_manager", ToolManager)
        toolset = _create_call_with_secret_toolset(secrets_dict, registry)
        tool_manager.register_toolset("secret_wrapper", toolset, enabled=False)

    registry.add_postinit(register_secret_toolset)

    def register_secret_toolset_plugin():
        lifecycle = registry.get_member_typechecked("lifecycle", Lifecycle)
        toolset_plugin = SecretToolsetPlugin(registry, secrets_dict)
        toolset_plugin.register(lifecycle)

    registry.add_postinit(register_secret_toolset_plugin)

    registry.add_postinit(register_plugin_to_lifecycle)

    return secret_plugin
