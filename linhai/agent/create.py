"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
from typing import TypedDict, Optional
import argparse
from datetime import datetime

from linhai.config import Config
from linhai.group_chat import GroupChat
from linhai.llm import LanguageModel, Message, OpenAi, SystemMessage, UserMessage

from linhai.tool.base import global_tools
from linhai.tool.main import ToolManager

from .conversation import register_conversation_folder
from linhai.utils import CliRuntimeNotice
from linhai.secret import initialize_secret_system

from .base import GlobalPrompt, PathPrompt

from .main import Agent


class AgentBuildContext(TypedDict):
    """Agent构建上下文，封装所有初始化Agent所需的数据。

    这是一个TypedDict，用于类型安全的参数传递。
    """

    group_chat: GroupChat
    config: Config
    config_basedir: Path
    llm_name: str
    max_toolcall_token_in_round: int
    checklist_path: Optional[Path]
    planning: bool
    cli_args: argparse.Namespace


def init_claw() -> None:
    """确保claw目录存在，并初始化五个核心markdown文档。"""
    from linhai.prompt import AGENTS_MD, BOOTSTRAP_MD, IDENTITY_MD, SOUL_MD, USER_MD

    claw_dir = Path.home() / ".local" / "share" / "linhai" / "claw"
    claw_dir.mkdir(parents=True, exist_ok=True)

    core_docs = [
        ("AGENTS.md", AGENTS_MD),
        ("BOOTSTRAP.md", BOOTSTRAP_MD),
        ("IDENTITY.md", IDENTITY_MD),
        ("SOUL.md", SOUL_MD),
        ("USER.md", USER_MD),
    ]

    for filename, content in core_docs:
        file_path = claw_dir / filename
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")


def create_agent_build_context(
    group_chat: GroupChat,
    config: Config,
    config_basedir: Path,
    cli_args: argparse.Namespace,
    planning: bool = False,
    llm_name: Optional[str] = None,
    checklist_path: Optional[Path] = None,
) -> AgentBuildContext:
    """创建Agent构建上下文，包含验证逻辑。"""

    llm_configs = config.llm
    llm_config_names = [llm_config.name for llm_config in llm_configs]

    if llm_name is None:

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
        else 30000
    )

    return {
        "group_chat": group_chat,
        "config": config,
        "config_basedir": config_basedir,
        "llm_name": resolved_llm_name,
        "max_toolcall_token_in_round": max_toolcall_token,
        "checklist_path": checklist_path,
        "planning": planning,
        "cli_args": cli_args,
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

    if context["cli_args"].claw:
        init_claw()

    llms = await _create_llm_instances(context)
    tool_manager, machine_control = await _create_tool_manager(context)

    from linhai.multimodal import MultimodalToolsetManager

    multimodal_manager = MultimodalToolsetManager(context["group_chat"])

    register_conversation_folder(context["group_chat"])

    agent = Agent(
        llms=llms,
        llm_name=context["llm_name"],
        compress_threshold=context["config"].agent.compress_threshold,
        group_chat=context["group_chat"],
        pinned_messages=await _create_pinned_messages(context),
        max_toolcall_token_in_round=context["max_toolcall_token_in_round"],
    )
    machine_control.register_plugin(agent.lifecycle)
    multimodal_manager.register_lifecycle(agent.lifecycle)
    tool_manager.register_lifecycle()

    if context["config"].agent.enable_directory_change_detection:
        from linhai.plugin import DirectoryChangePlugin

        DirectoryChangePlugin(context["group_chat"]).register(agent.lifecycle)

    if context["config"].agent.allowed_commands:
        from linhai.plugin import CommandWhitelistPlugin

        CommandWhitelistPlugin(context["group_chat"], context["config"]).register(
            agent.lifecycle
        )

    from linhai.plugin import MachineControlIntroductionPlugin

    MachineControlIntroductionPlugin(context["group_chat"]).register(agent.lifecycle)

    if context.get("planning", False):
        from linhai.plugin.planning import (
            PlanningStatusReminderPlugin,
            UserInputRuntimeMessagePlugin,
        )

        PlanningStatusReminderPlugin(context["group_chat"]).register(agent.lifecycle)
        UserInputRuntimeMessagePlugin(context["group_chat"]).register(agent.lifecycle)

    if context["cli_args"].claw:
        from linhai.plugin.claw import ClawPlugin

        ClawPlugin(context["group_chat"], context["cli_args"]).register(agent.lifecycle)

    return agent


async def _create_llm_instances(context: "AgentBuildContext") -> list[LanguageModel]:

    llms = []
    for llm_config in context["config"].llm:
        llm = OpenAi(
            group_chat=context["group_chat"],
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config.client_options,
            chat_completion_kwargs=llm_config.completion_options,
            token_limit=llm_config.token_limit,
            compatibility=llm_config.compatibility,
            name=llm_config.name,
            support_image=llm_config.support_image,
        )
        llms.append(llm)
    return llms


async def _create_tool_manager(context: "AgentBuildContext"):
    from linhai.machine_control import MachineControl

    tool_manager = ToolManager(
        group_chat=context["group_chat"],
        toolsets=[global_tools],
        config=context["config"].tools,
        mcp_config=context["config"].agent.mcp,
        mcp_basedir=context["config_basedir"],
    )

    machine_control = MachineControl(context["group_chat"])

    if context["config"].tools.secret.config_path:
        initialize_secret_system(
            group_chat=context["group_chat"],
            secret_config_path=context["config"].tools.secret.config_path,
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

    pinned_messages: list[Message] = [SystemMessage(context["group_chat"])]
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pinned_messages.append(RuntimeMessage(f"Agent启动时间: {startup_time}"))

    cli_args = context["cli_args"]

    if context["config"].user_prompt and context["config_basedir"]:
        prompt_file_path = (
            context["config_basedir"] / context["config"].user_prompt.file_path
        )
        pinned_messages.append(GlobalPrompt(Path(prompt_file_path).absolute()))
    else:
        pinned_messages.append(
            GlobalPrompt(Path("~/.config/linhai/AGENTS.md").expanduser())
        )

    if context["checklist_path"]:
        from .base import ChecklistMessage

        pinned_messages.append(ChecklistMessage(context["checklist_path"]))
        await context["group_chat"].send_if_exists(
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

    from linhai.agent.base import FileContentMessage

    if context.get("planning", False):
        from .planning import setup_planning_for_agent

        planning_message = setup_planning_for_agent(context)
        pinned_messages.append(planning_message)

    if cli_args.message:
        for msg in cli_args.message:
            pinned_messages.append(UserMessage(msg))

    if not cli_args.file:
        return pinned_messages

    for file_path in cli_args.file:
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
