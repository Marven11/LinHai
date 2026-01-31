"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
from typing import Literal, TypedDict, Optional
import argparse

from linhai.config import AgentConfig, Config, MCPConfig, ToolConfig
from linhai.group_chat import GroupChat
from linhai.llm import LanguageModel, Message, OpenAi, SystemMessage, UserMessage
from linhai.subagent import SubAgentManager
from linhai.subagent.issue import IssueManager
from linhai.tool.base import global_tools
from linhai.tool.main import ToolManager
from linhai.tool.general import TodolistManager
from .conversation import register_conversation_folder
from linhai.utils import CliRuntimeNotice
from linhai.secret import initialize_secret_system

from .base import GlobalMemory, PathMemory

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
    git_diff_reviewer: bool
    violation_checker: bool
    cli_args: argparse.Namespace


def create_agent_build_context(
    group_chat: GroupChat,
    config: Config,
    config_basedir: Path,
    git_diff_reviewer: bool,
    violation_checker: bool,
    cli_args: argparse.Namespace,
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
        "git_diff_reviewer": git_diff_reviewer,
        "violation_checker": violation_checker,
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
    from .main import Agent

    llms = await _create_llm_instances(context)
    tool_manager, machine_control = await _create_tool_manager(context)
    todolist_manager = TodolistManager(context["group_chat"])

    from linhai.multimodal import MultimodalToolsetManager
    multimodal_manager = MultimodalToolsetManager(context["group_chat"])

    register_conversation_folder(context["group_chat"])
    
    agent = Agent(
        llms=llms,
        llm_name=context["llm_name"],
        compress_threshold=context["config"].agent.compress_threshold,
        group_chat=context["group_chat"],
        init_messages=await _create_init_messages(context),
        max_toolcall_token_in_round=context["max_toolcall_token_in_round"],
    )
    machine_control.register_plugin(agent.lifecycle)
    multimodal_manager.register_lifecycle(agent.lifecycle)
    tool_manager.register_lifecycle()
    if context["config"].agent.enable_task_planning:
        from .planning import TaskPlanningPromptPlugin, TaskPlanningEnforcementPlugin

        TaskPlanningPromptPlugin(context["group_chat"]).register(agent.lifecycle)
        TaskPlanningEnforcementPlugin(context["group_chat"]).register(agent.lifecycle)
    if context["config"].agent.enable_directory_change_detection:
        from linhai.plugin import DirectoryChangePlugin

        DirectoryChangePlugin(context["group_chat"]).register(agent.lifecycle)

    # 注册CommandWhitelistPlugin如果配置了allowed_commands
    if context["config"].agent.allowed_commands:
        from linhai.plugin import CommandWhitelistPlugin

        CommandWhitelistPlugin(context["group_chat"], context["config"]).register(
            agent.lifecycle
        )

    await _create_subagent(context, llms, agent)
    return agent


async def _create_subagent(
    context: AgentBuildContext, llms: list[LanguageModel], agent: Agent
) -> None:
    if context["git_diff_reviewer"]:
        from linhai.subagent.subagent_types.git_diff_reviewer import GitDiffReviewPlugin

        GitDiffReviewPlugin(context["group_chat"]).register(agent.lifecycle)

    if context["violation_checker"]:
        from linhai.subagent.subagent_types.violation_checker import (
            ViolationCheckerPlugin,
        )

        ViolationCheckerPlugin(context["group_chat"]).register(agent.lifecycle)

    if context["config"].subagent and context["config"].subagent.enable:
        from linhai.subagent import SubAgentManager
        from linhai.subagent.issue import IssueManager

        subagent_manager = SubAgentManager(
            context["group_chat"], context["config"].subagent, llms
        )
        issue_manager = IssueManager(context["group_chat"])


async def _create_llm_instances(context: "AgentBuildContext") -> list[LanguageModel]:

    async def notification_callback(
        level: Literal["INFO", "WARNING", "ERROR"], content: str
    ) -> None:
        notice = CliRuntimeNotice(level=level, content=content)
        await context["group_chat"].send_if_exists("ui_log", notice)

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


async def _create_init_messages(context: "AgentBuildContext") -> list[Message]:
    """创建初始化消息列表。

    Args:
        context: Agent构建上下文

    Returns:
        初始化消息列表
    """
    init_messages: list[Message] = [SystemMessage(context["group_chat"])]

    cli_args = context["cli_args"]

    if context["config"].memory and context["config_basedir"]:
        memory_file_path = (
            context["config_basedir"] / context["config"].memory.file_path
        )
        init_messages.append(GlobalMemory(Path(memory_file_path).absolute()))
    else:
        init_messages.append(
            GlobalMemory(Path("~/.config/linhai/LINHAI.md").expanduser())
        )

    if context["checklist_path"]:
        from .base import ChecklistMessage

        init_messages.append(ChecklistMessage(context["checklist_path"]))
        await context["group_chat"].send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"已加载检查清单文件: {context["checklist_path"]}",
            ),
        )

    project_memory_filepaths = [
        Path("./LINHAI.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    for filepath in project_memory_filepaths:
        if filepath.exists():
            init_messages.append(PathMemory(filepath))

    from linhai.llm import UserMessage
    from linhai.agent.base import FileContentMessage

    if cli_args.message:
        for msg in cli_args.message:
            init_messages.append(UserMessage(msg))

    if not cli_args.file:
        return init_messages

    for file_path in cli_args.file:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            init_messages.append(
                FileContentMessage(
                    filepath=str(file_path),
                    content=content,
                    show_line_numbers=False,
                )
            )

    return init_messages
