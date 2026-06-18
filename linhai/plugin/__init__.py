"""Plugin系统模块。"""

from .message_checkers import Plugin
from .message_checkers import (
    WaitingUserPlugin,
    WaitingUserReminderPlugin,
    WrongEndPlugin,
    EndThinkPlugin,
    OnlyReasoningPlugin,
    PreviousReasoningPlugin,
    JsonCodeBlockPlugin,
    KimiK25ToolCallPlugin,
    MinimaxToolCallPlugin,
    RuntimeImitationPlugin,
    VolcanoDeepseekFixPlugin,
    GlmToolCallPlugin,
    GlmInsultMaskPlugin,
    MisplacedToolCallPlugin,
    HackerNewsPlugin,
    CsdnWarningPlugin,
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
    SedFragmentedReadPlugin,
)

from .security_config import (
    WithSecretParameterPositionPlugin,
    MissingWithSecretWarningPlugin,
    CommandWhitelistPlugin,
    ProcessArgvCheckerPlugin,
)

from .file_permission_plugin import FileOperationPermissionPlugin

from .sudo_stdio_checker import SudoStdioCheckerPlugin
from .command_hints import (
    SudoBashHintPlugin,
    StdioCommandCheckerPlugin,
    PkillCheckerPlugin,
)

from .afk_plugin import AfkPlugin
from .claw import ClawHeartbeatPlugin
from .system_message_leaning import (
    MachineControlIntroductionPlugin,
    CurrentDirectoryPlugin,
    NativeToolcallFormatPlugin,
)
from .planning import (
    TodolistCheckerPlugin,
    PlanningHeadingCheckPlugin,
    DeepseekTodolistProtectionPlugin,
    PlanningChecklistPlugin,
)
from .reminder import ReminderPlugin, ReminderWriteGuardPlugin
from .python_chore import PythonCommentCheckerPlugin
from .telegram import TelegramReactionReminderPlugin
from .catgirl_tone import CatgirlTonePlugin
from .interlink import InterlinkPlugin

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
    "WaitingUserReminderPlugin",
    "WrongEndPlugin",
    "EndThinkPlugin",
    "OnlyReasoningPlugin",
    "PreviousReasoningPlugin",
    "JsonCodeBlockPlugin",
    "KimiK25ToolCallPlugin",
    "MinimaxToolCallPlugin",
    "RuntimeImitationPlugin",
    "GlmToolCallPlugin",
    "GlmInsultMaskPlugin",
    "MisplacedToolCallPlugin",
    "PromptFastAgentPlugin",
    "SlowStartPlugin",
    "WeirdTokenPlugin",
    "SingleToolCallReminderPlugin",
    "ToolCallInReasoningPlugin",
    "DuplicateFileReadPlugin",
    "UnnecessarySedReadPlugin",
    "UnnecessaryRunCommandPlugin",
    "FileReadWriteConflictPlugin",
    "SedFragmentedReadPlugin",
    "WithSecretParameterPositionPlugin",
    "MissingWithSecretWarningPlugin",
    "CommandWhitelistPlugin",
    "ProcessArgvCheckerPlugin",
    "FileOperationPermissionPlugin",
    "AfkPlugin",
    "ClawHeartbeatPlugin",
    "VolcanoDeepseekFixPlugin",
    "MachineControlIntroductionPlugin",
    "CurrentDirectoryPlugin",
    "TodolistCheckerPlugin",
    "PlanningHeadingCheckPlugin",
    "DeepseekTodolistProtectionPlugin",
    "PlanningChecklistPlugin",
    "ReminderPlugin",
    "ReminderWriteGuardPlugin",
    "is_small_file",
    "is_already_read",
    "is_existing_file",
    "JsonValue",
    "READ_FILE_COMMANDS",
    "PythonCommentCheckerPlugin",
    "CatgirlTonePlugin",
    "HackerNewsPlugin",
    "CsdnWarningPlugin",
    "SudoBashHintPlugin",
    "StdioCommandCheckerPlugin",
    "PkillCheckerPlugin",
    "NativeToolcallFormatPlugin",
    "TelegramReactionReminderPlugin",
    "InterlinkPlugin",
]
