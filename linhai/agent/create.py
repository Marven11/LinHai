"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
from typing import TypedDict, Optional, Tuple, Union, Literal
import argparse
from datetime import datetime

import platform

from linhai.config import (
    AgentConfig,
    BubblewrapConfig,
    Config,
    LLMConfig,
    MacOsSandboxConfig,
    MCPConfig,
    ProcessSandboxConfig,
    ToolConfig,
)
from linhai.registry import Registry
from linhai.llm import Message, OpenAi, SystemMessage, UserMessage
from linhai.llm_manager import LlmManager

from linhai.tool.base import utils_tools
from linhai.tool.main import ToolManager
from linhai.config import AVAILABLE_TOOLSETS


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linhai.machine_control import MachineControl

from .conversation import register_conversation_folder
from linhai.utils import CliRuntimeNotice
from linhai.secret import initialize_secret_system

from linhai.sandbox import BubbleWrapSandbox, MacOsSandbox, NoSandbox
from .base import GlobalPrompt, PathPrompt

from .main import Agent
from .orchestration import AgentContextOrchestration


class TelegramContext(TypedDict):
    """Telegram配置上下文。"""

    bot_token: str
    default_chat_id: str


class AgentBuildContext(TypedDict):
    """Agent构建上下文，封装所有初始化Agent所需的数据。

    这是一个TypedDict，用于类型安全的参数传递。
    """

    registry: Registry
    config_basedir: Optional[Path]
    llms: list[LLMConfig]
    llm_name: str
    max_toolcall_token_in_round: int | float
    checklist_path: Optional[Path]
    user_prompt: Optional[str]
    planning: bool
    toolsets_config: Union[Literal["defaults"], list[str]]
    override_toolsets: Optional[list[str]]
    compress_threshold: Union[int, float]
    enable_directory_change_detection: bool
    max_toolcall_for_llm: dict[str, int]
    allowed_commands: list[list[str]]
    telegram_config: Optional[TelegramContext]
    mcp_configs: list["MCPConfig"]
    tool_config: "ToolConfig"
    secret_config_path: Optional[str]
    rss: list[str]
    telegram: bool
    disable_waiting_marker: bool
    afk: bool
    claw_enabled: bool
    claw_folder: Optional[Path]
    message: list[str]
    file: list[Path]
    process_sandbox: Optional[Union[MacOsSandboxConfig, BubblewrapConfig]]


def _resolve_agent_profile(config: Config, profile_name: Optional[str]) -> AgentConfig:
    """根据profile名称解析并返回对应的AgentConfig。"""
    if not config.agent:
        raise ValueError("配置中没有定义任何agent profile")

    if profile_name is None:
        return config.agent[0]

    for agent_config in config.agent:
        if agent_config.name == profile_name:
            return agent_config

    available_profiles = ", ".join(a.name for a in config.agent)
    raise ValueError(
        f"Agent profile '{profile_name}' 不存在。可用的profile包括: {available_profiles}"
    )


def _resolve_process_sandbox(
    process_sandbox: Optional[ProcessSandboxConfig],
) -> Optional[Union[MacOsSandboxConfig, BubblewrapConfig]]:
    if process_sandbox is None:
        return None
    system = platform.system()
    if system == "Darwin" and process_sandbox.macos_sandbox is not None:
        return process_sandbox.macos_sandbox
    if system == "Linux" and process_sandbox.bubblewrap is not None:
        return process_sandbox.bubblewrap
    return None


def create_agent_build_context(
    registry: Registry,
    config: Config,
    config_basedir: Optional[Path],
    cli_args: argparse.Namespace,
    planning: bool = False,
    llm_name: Optional[str] = None,
    checklist_path: Optional[Path] = None,
    profile_name: Optional[str] = None,
) -> AgentBuildContext:
    """创建Agent构建上下文，包含验证逻辑。"""

    agent_config = _resolve_agent_profile(config, profile_name)

    llm_configs = config.llm
    llm_config_names = [llm_config.name for llm_config in llm_configs]

    if llm_name is None:
        config_default_llm = agent_config.default_llm
        if config_default_llm is not None:
            if config_default_llm not in llm_config_names:
                available_llms = ", ".join(llm_config_names)
                raise ValueError(
                    f"agent.default_llm配置的LLM名称 '{config_default_llm}' 不存在。可用的LLM包括: {available_llms}"
                )
            resolved_llm_name = config_default_llm
        else:
            if not llm_config_names:
                raise ValueError("配置中没有可用的LLM")
            resolved_llm_name = llm_config_names[0]
    elif llm_name not in llm_config_names:
        available_llms = ", ".join(llm_config_names)
        raise ValueError(
            f"LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"
        )
    else:
        resolved_llm_name = llm_name

    max_toolcall_token = (
        config.tools.max_toolcall_token_in_round
        if config.tools.max_toolcall_token_in_round is not None
        else 0.3
    )

    user_prompt: Optional[str] = None
    if config.user_prompt and config.user_prompt.file_path:
        if config_basedir is None:
            raise ValueError("User prompt file需要config_basedir")
        user_prompt = str((config_basedir / config.user_prompt.file_path).absolute())

    telegram_config: Optional[TelegramContext] = None
    if config.remote_control.telegram:
        telegram_config = TelegramContext(
            bot_token=config.remote_control.telegram.bot_token,
            default_chat_id=config.remote_control.telegram.default_chat_id,
        )

    return {
        "registry": registry,
        "config_basedir": config_basedir,
        "llms": config.llm,
        "llm_name": resolved_llm_name,
        "max_toolcall_token_in_round": max_toolcall_token,
        "checklist_path": checklist_path,
        "user_prompt": user_prompt,
        "planning": planning,
        "toolsets_config": config.tools.toolsets,
        "override_toolsets": agent_config.override_toolsets,
        "compress_threshold": agent_config.compress_threshold,
        "enable_directory_change_detection": agent_config.enable_directory_change_detection,
        "max_toolcall_for_llm": agent_config.max_toolcall_for_llm,
        "allowed_commands": agent_config.allowed_commands,
        "telegram_config": telegram_config,
        "mcp_configs": agent_config.mcp,
        "tool_config": config.tools,
        "secret_config_path": (
            config.tools.secret.config_path if config.tools.secret else None
        ),
        "rss": cli_args.rss,
        "telegram": cli_args.telegram,
        "disable_waiting_marker": cli_args.disable_waiting_marker,
        "afk": cli_args.afk,
        "claw_enabled": cli_args.claw,
        "claw_folder": cli_args.claw_folder,
        "message": cli_args.message,
        "file": cli_args.file,
        "process_sandbox": _resolve_process_sandbox(agent_config.process_sandbox),
    }


async def create_agent_from_config(
    context: AgentBuildContext,
) -> Agent:
    """创建Agent实例（从配置对象）

    Args:
        context: Agent构建上下文

    Returns:
        Agent实例
    """

    from linhai.multimodal import MultimodalToolsetManager

    multimodal_manager = MultimodalToolsetManager(context["registry"])
    llm_manager = await _create_llm_instances(context)
    tool_manager, machine_control = await _create_tool_manager(
        context, multimodal_manager.toolset
    )

    toolsets_config = context["toolsets_config"]
    override_toolsets = context["override_toolsets"]

    if override_toolsets is not None:
        enabled_toolsets = list(override_toolsets)
    elif toolsets_config == "defaults" or not isinstance(toolsets_config, (str, list)):
        enabled_toolsets = list(AVAILABLE_TOOLSETS)
    else:
        enabled_toolsets = list(toolsets_config)

    register_conversation_folder(context["registry"])

    agent = Agent(
        llm_manager=llm_manager,
        compress_threshold=context["compress_threshold"],
        registry=context["registry"],
        pinned_messages=await _create_pinned_messages(context),
        max_toolcall_token_in_round=context["max_toolcall_token_in_round"],
    )
    orchestration = context["registry"].get_member_typechecked(
        "agent_context_orchestration", AgentContextOrchestration
    )
    if "context_cleaning" in enabled_toolsets:
        tool_manager.add_toolset(orchestration.get_context_cleaning_toolset())
    if "llm" in enabled_toolsets:
        tool_manager.add_toolset(agent.toolcall_processor.calculate_llm_toolset())
    if machine_control is not None:
        machine_control.register_plugin(agent.lifecycle)
    multimodal_manager.register_lifecycle(agent.lifecycle)
    tool_manager.register_lifecycle()

    if context["enable_directory_change_detection"]:
        from linhai.plugin import DirectoryChangePlugin

        DirectoryChangePlugin(context["registry"]).register(agent.lifecycle)

    if context["allowed_commands"]:
        from linhai.plugin import CommandWhitelistPlugin

        CommandWhitelistPlugin(
            context["registry"], context["allowed_commands"]
        ).register(agent.lifecycle)

    from linhai.plugin import MachineControlIntroductionPlugin
    from linhai.rss import RssPlugin

    MachineControlIntroductionPlugin(context["registry"]).register(agent.lifecycle)

    if context["rss"]:
        RssPlugin(
            context["registry"],
            context["rss"],
            30,
        ).register(agent.lifecycle)

    telegram_config = context["telegram_config"]
    if telegram_config and context["telegram"]:
        from linhai.plugin.telegram import TelegramPlugin

        TelegramPlugin(context["registry"], telegram_config).register(agent.lifecycle)

    if context.get("planning", False):
        from linhai.plugin.planning import (
            PlanningStatusReminderPlugin,
            UserInputRuntimeMessagePlugin,
            DesignMdReminderPlugin,
        )

        PlanningStatusReminderPlugin(context["registry"]).register(agent.lifecycle)
        UserInputRuntimeMessagePlugin(context["registry"]).register(agent.lifecycle)
        DesignMdReminderPlugin(context["registry"]).register(agent.lifecycle)

    if context["claw_enabled"]:
        from linhai.plugin.claw import ClawPlugin

        ClawPlugin(context["registry"], context["claw_folder"]).register(
            agent.lifecycle
        )

    if context["afk"]:
        from linhai.plugin import AfkPlugin

        AfkPlugin(context["registry"], afk=True).register(agent.lifecycle)

    if not context["disable_waiting_marker"]:
        from linhai.plugin.message_checkers import WaitingUserPlugin

        WaitingUserPlugin(context["registry"]).register(agent.lifecycle)

    if context["max_toolcall_for_llm"]:
        from linhai.plugin import PromptFastAgentPlugin

        plugin = PromptFastAgentPlugin(
            context["registry"], context["max_toolcall_for_llm"]
        )
        plugin.register(agent.lifecycle)

    _register_sandbox(context["registry"], context["process_sandbox"])

    _register_default_plugins(agent.lifecycle)

    return agent


def _build_explicit_cache_info(llm_config):
    from linhai.llm import ExplicitCacheInfo

    if llm_config.explicit_cache is None or not llm_config.explicit_cache.enable:
        return None
    return ExplicitCacheInfo(
        cache_write_price_ratio=llm_config.explicit_cache.cache_write_price_ratio,
        cache_hit_price_ratio=llm_config.explicit_cache.cache_hit_price_ratio,
    )


async def _create_llm_instances(context: "AgentBuildContext") -> LlmManager:

    llms = []
    for llm_config in context["llms"]:
        llm = OpenAi(
            registry=context["registry"],
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config.client_options,
            chat_completion_kwargs=llm_config.completion_options,
            token_limit=llm_config.token_limit,
            compatibility=llm_config.compatibility,
            name=llm_config.name,
            support_image=llm_config.support_image,
            explicit_cache_info=_build_explicit_cache_info(llm_config),
        )
        llms.append(llm)

    llm_fallback_map = {}
    for llm_config in context["llms"]:
        if llm_config.fallback is not None:
            llm_fallback_map[llm_config.name] = llm_config.fallback
        else:
            llm_fallback_map[llm_config.name] = None

    llm_manager = LlmManager(
        registry=context["registry"],
        llms=llms,
        default_llm_name=context["llm_name"],
        llm_fallback_map=llm_fallback_map,
    )
    return llm_manager


def _build_toolsets_from_config(
    context: "AgentBuildContext", multimodal_toolset
) -> Tuple[list, Optional["MachineControl"]]:
    """根据配置构建toolsets列表"""
    from linhai.machine_control.main import register_machine_control_tools
    from linhai.tool.general import generate_sleep_toolset

    registry = context["registry"]
    toolsets_config = context["toolsets_config"]
    override_toolsets = context["override_toolsets"]

    if override_toolsets is not None:
        enabled_toolsets = list(override_toolsets)
    elif toolsets_config == "defaults" or not isinstance(toolsets_config, (str, list)):
        enabled_toolsets = list(AVAILABLE_TOOLSETS)
    else:
        enabled_toolsets = list(toolsets_config)

    toolsets = []
    machine_control = None

    if "utils" in enabled_toolsets:
        toolsets.append(utils_tools)

    if "sleep" in enabled_toolsets:
        toolsets.append(generate_sleep_toolset(registry))

    if "machine_control" in enabled_toolsets:
        from linhai.machine_control import MachineControl

        machine_control = MachineControl(registry)
        toolsets.append(register_machine_control_tools(machine_control))

    if "multimodal" in enabled_toolsets:
        toolsets.append(multimodal_toolset)

    return toolsets, machine_control


async def _create_tool_manager(context: "AgentBuildContext", multimodal_toolset):
    from linhai.tool.mcp_connector import MCPConnector

    toolsets, machine_control = _build_toolsets_from_config(context, multimodal_toolset)

    mcp_connector = MCPConnector(context["registry"])
    if context["mcp_configs"] and context["config_basedir"] is not None:
        from contextlib import AsyncExitStack

        for mcp_config in context["mcp_configs"]:
            server_script_path = (
                context["config_basedir"] / mcp_config.server_script_path
            )
            exit_stack = AsyncExitStack()
            await mcp_connector.connect_mcp_server(
                mcp_config.name, server_script_path.absolute().as_posix(), exit_stack
            )

    tool_manager = ToolManager(
        registry=context["registry"],
        toolsets=toolsets,
        config=context["tool_config"],
        mcp_connector=mcp_connector,
    )

    if context["secret_config_path"]:
        initialize_secret_system(
            registry=context["registry"],
            secret_config_path=context["secret_config_path"],
            config_basedir=context["config_basedir"],
        )

    return tool_manager, machine_control


async def _create_pinned_messages(context: "AgentBuildContext") -> list[Message]:
    """创建固定消息列表。

    Args:
        context: Agent构建上下文

    Returns:
        固定消息列表
    """
    from linhai.agent.base import RuntimeMessage

    pinned_messages: list[Message] = [SystemMessage(context["registry"])]
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pinned_messages.append(RuntimeMessage(f"Agent启动时间: {startup_time}"))

    if context["user_prompt"] is not None:
        pinned_messages.append(GlobalPrompt(Path(context["user_prompt"])))
    else:
        pinned_messages.append(
            GlobalPrompt(Path("~/.config/linhai/AGENTS.md").expanduser())
        )

    if context["checklist_path"]:
        from .base import ChecklistMessage

        pinned_messages.append(ChecklistMessage(context["checklist_path"]))
        await context["registry"].send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"已加载检查清单文件: {context["checklist_path"]}",
            ),
        )

    project_prompt_filepaths = [
        Path("./AGENTS.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    for filepath in project_prompt_filepaths:
        if filepath.exists():
            pinned_messages.append(PathPrompt(filepath))

    if context.get("planning", False):
        from .planning import setup_planning_for_agent

        planning_message = setup_planning_for_agent(context)
        pinned_messages.append(planning_message)

    if context["message"]:
        for msg in context["message"]:
            pinned_messages.append(UserMessage(msg))

    if context["file"]:
        from linhai.agent.base import FileContentMessage

        for file_path in context["file"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                pinned_messages.append(
                    FileContentMessage(
                        filepath=str(file_path),
                        content=content,
                        show_line_numbers=False,
                    )
                )

    return pinned_messages


def _register_sandbox(
    registry: Registry,
    sandbox_config: Optional[Union[MacOsSandboxConfig, BubblewrapConfig]],
) -> None:
    if sandbox_config is None:
        sandbox = NoSandbox()
    elif isinstance(sandbox_config, MacOsSandboxConfig):
        sandbox = MacOsSandbox(sandbox_config.sandbox_profile)
    else:
        sandbox = BubbleWrapSandbox(sandbox_config.argv)
    registry.register_member("process_sandbox", sandbox)


def _register_default_plugins(lifecycle):
    """注册默认的Plugin。"""
    from linhai.plugin import (
        WrongEndPlugin,
        SlowStartPlugin,
        WeirdTokenPlugin,
        EndThinkPlugin,
        OnlyReasoningPlugin,
        ToolCallInReasoningPlugin,
        SingleToolCallReminderPlugin,
        JsonCodeBlockPlugin,
        RuntimeImitationPlugin,
        UnnecessarySedReadPlugin,
        UnnecessaryRunCommandPlugin,
        FileReadWriteConflictPlugin,
        KimiK25ToolCallPlugin,
        MinimaxToolCallPlugin,
        GlmToolCallPlugin,
        GlmInsultMaskPlugin,
        MissingWithSecretWarningPlugin,
        TodolistCheckerPlugin,
        VolcanoDeepseekFixPlugin,
        ProcessArgvCheckerPlugin,
        SudoStdioCheckerPlugin,
    )
    from .orchestration import RedStateToolBlockPlugin, NotificationMessagePlugin

    plugins = [
        WrongEndPlugin(lifecycle.registry),
        SlowStartPlugin(lifecycle.registry),
        WeirdTokenPlugin(lifecycle.registry),
        EndThinkPlugin(lifecycle.registry),
        OnlyReasoningPlugin(lifecycle.registry),
        ToolCallInReasoningPlugin(lifecycle.registry),
        SingleToolCallReminderPlugin(lifecycle.registry),
        JsonCodeBlockPlugin(lifecycle.registry),
        RuntimeImitationPlugin(lifecycle.registry),
        UnnecessarySedReadPlugin(lifecycle.registry),
        UnnecessaryRunCommandPlugin(lifecycle.registry),
        RedStateToolBlockPlugin(lifecycle.registry),
        NotificationMessagePlugin(lifecycle.registry),
        FileReadWriteConflictPlugin(lifecycle.registry),
        KimiK25ToolCallPlugin(lifecycle.registry),
        MinimaxToolCallPlugin(lifecycle.registry),
        GlmToolCallPlugin(lifecycle.registry),
        GlmInsultMaskPlugin(lifecycle.registry),
        MissingWithSecretWarningPlugin(lifecycle.registry),
        VolcanoDeepseekFixPlugin(lifecycle.registry),
        ProcessArgvCheckerPlugin(lifecycle.registry),
        SudoStdioCheckerPlugin(lifecycle.registry),
        TodolistCheckerPlugin(lifecycle.registry),
    ]

    for plugin in plugins:
        plugin.register(lifecycle)
