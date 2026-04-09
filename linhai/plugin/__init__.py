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
    GlmToolCallPlugin,
    GlmInsultMaskPlugin,
    MisplacedToolCallPlugin,
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
)

from .security_config import (
    WithSecretParameterPositionPlugin,
    MissingWithSecretWarningPlugin,
    CommandWhitelistPlugin,
    ProcessArgvCheckerPlugin,
)

from .sudo_stdio_checker import SudoStdioCheckerPlugin

from .afk_plugin import AfkPlugin
from .claw import ClawHeartbeatPlugin
from .system_message_leaning import MachineControlIntroductionPlugin
from .planning import TodolistCheckerPlugin
from .reminder import ReminderPlugin, ReminderWriteGuardPlugin
from .python_chore import PythonCommentCheckerPlugin
from .catgirl_tone import CatgirlTonePlugin

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
    "WithSecretParameterPositionPlugin",
    "MissingWithSecretWarningPlugin",
    "CommandWhitelistPlugin",
    "ProcessArgvCheckerPlugin",
    "AfkPlugin",
    "ClawHeartbeatPlugin",
    "VolcanoDeepseekFixPlugin",
    "MachineControlIntroductionPlugin",
    "TodolistCheckerPlugin",
    "ReminderPlugin",
    "ReminderWriteGuardPlugin",
    "is_small_file",
    "is_already_read",
    "is_existing_file",
    "JsonValue",
    "READ_FILE_COMMANDS",
    "PythonCommentCheckerPlugin",
    "CatgirlTonePlugin",
]
