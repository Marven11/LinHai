"""Plugin系统模块。"""

from .message_checkers import Plugin
from .message_checkers import (
    WaitingUserPlugin,
    WrongEndPlugin,
    EndThinkPlugin,
    OnlyReasoningPlugin,
    PreviousReasoningPlugin,
    JsonCodeBlockPlugin,
    KimiK25ToolCallPlugin,
    MinimaxToolCallPlugin,
    RuntimeImitationPlugin,
    VolcanoDeepseekFixPlugin,
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

from .sudo_stdio_checker import SudoStdioCheckerPlugin

from .afk_plugin import AfkPlugin
from .system_message_leaning import MachineControlIntroductionPlugin
from .planning import TodolistCheckerPlugin

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
    "MinimaxToolCallPlugin",
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
    "VolcanoDeepseekFixPlugin",
    "MachineControlIntroductionPlugin",
    "TodolistCheckerPlugin",
    "is_small_file",
    "is_already_read",
    "is_existing_file",
    "JsonValue",
    "READ_FILE_COMMANDS",
]
