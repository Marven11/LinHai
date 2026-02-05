"""Plugin系统模块。"""

# 重新导出所有插件，保持向后兼容
from .message_checkers import Plugin  # Plugin基类
from .message_checkers import (
    WaitingUserPlugin,
    WrongEndPlugin,
    EndThinkPlugin,
    OnlyReasoningPlugin,
    PreviousReasoningPlugin,
    JsonCodeBlockPlugin,
    KimiK25ToolCallPlugin,
    RuntimeImitationPlugin,
)

from .tool_call_managers import (
    PromptFastAgentPlugin,
    SlowStartPlugin,
    WeirdTokenPlugin,
    SingleToolCallReminderPlugin,
    ToolCallInReasoningPlugin,
)

from .file_operations import (
    DuplicateFileReadPlugin,
    UnnecessarySedReadPlugin,
    UnnecessaryRunCommandPlugin,
    FileReadWriteConflictPlugin,
    DirectoryChangePlugin,
)

from .security_config import (
    WithSecretParameterPositionPlugin,
    MissingWithSecretWarningPlugin,
    CommandWhitelistPlugin,
    ProcessArgvCheckerPlugin,
)

from .afk_plugin import AfkPlugin

from .helpers import (
    is_small_file,
    is_already_read,
    is_existing_file,
    JsonValue,
    READ_FILE_COMMANDS,
)

__all__ = [
    "Plugin",
    "WaitingUserPlugin",
    "WrongEndPlugin",
    "EndThinkPlugin",
    "OnlyReasoningPlugin",
    "PreviousReasoningPlugin",
    "JsonCodeBlockPlugin",
    "KimiK25ToolCallPlugin",
    "RuntimeImitationPlugin",
    "PromptFastAgentPlugin",
    "SlowStartPlugin",
    "WeirdTokenPlugin",
    "SingleToolCallReminderPlugin",
    "ToolCallInReasoningPlugin",
    "DuplicateFileReadPlugin",
    "UnnecessarySedReadPlugin",
    "UnnecessaryRunCommandPlugin",
    "FileReadWriteConflictPlugin",
    "DirectoryChangePlugin",
    "WithSecretParameterPositionPlugin",
    "MissingWithSecretWarningPlugin",
    "CommandWhitelistPlugin",
    "ProcessArgvCheckerPlugin",
    "AfkPlugin",
    "is_small_file",
    "is_already_read",
    "is_existing_file",
    "JsonValue",
    "READ_FILE_COMMANDS",
]
