"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
from typing import Literal

from linhai.config import AgentConfig, Config, MCPConfig, ToolConfig
from linhai.group_chat import GroupChat
from linhai.llm import LanguageModel, Message, OpenAi, SystemMessage
from linhai.subagent import SubAgentManager
from linhai.subagent.issue import IssueManager
from linhai.subagent.tools import create_subagent_toolset
from linhai.tool.base import global_tools
from linhai.tool.main import ToolManager
from linhai.tool.general import TodolistManager, create_agent_todolist_toolset
from linhai.utils import CliRuntimeNotice
from linhai.machine_control.main import register_machine_control_tools

from .base import AgentContext, GlobalMemory
from .issue_tools import create_issue_toolset


async def create_agent_from_config(
    group_chat: GroupChat,
    config: Config,
    llm_name: str | None = None,
    config_basedir: Path | None = None,
    checklist_path: Path | None = None,
):
    """创建Agent实例（从配置对象）

    Args:
        group_chat: GroupChat实例
        config: 配置对象
        llm_name: 指定的LLM名称（可选）
        config_basedir: 配置文件所在目录（用于解析相对路径）

    Returns:
        Agent实例
    """
    from .main import Agent  # 避免循环导入

    agent_config = config.agent if config.agent else AgentConfig()
    tools_config = config.tools if config.tools else ToolConfig()

    llms = await _create_llm_instances(config.llm, group_chat)

    llm_names = [llm_config.name for llm_config in config.llm]
    agent_context = await _create_agent_context(
        llms=llms,
        llm_names=llm_names,
        llm_name=llm_name,
        agent_config=agent_config,
    )

    tool_manager, machine_control = await _create_tool_manager(
        group_chat,
        tools_config,
        agent_config.mcp if agent_config else [],
        mcp_basedir=config_basedir or Path.cwd(),
    )

    todolist_manager = TodolistManager(group_chat)
    todolist_toolset = create_agent_todolist_toolset(todolist_manager)
    tool_manager.add_toolset(todolist_toolset)

    memory_file_path = None
    if config.memory and config_basedir:
        memory_file_path = config_basedir / config.memory.file_path

    init_messages = await _create_init_messages(
        group_chat=group_chat,
        memory_file_path=memory_file_path,
        checklist_path=checklist_path,
    )

    agent = Agent(
        context=agent_context,
        group_chat=group_chat,
        init_messages=init_messages,
    )

    # 注册MachineControl插件
    machine_control.register_plugin(agent.lifecycle)
    tool_manager.register_lifecycle()

    subagent_config = config.subagent
    if subagent_config and subagent_config.enable:
        subagent_manager = SubAgentManager(group_chat, subagent_config, llms, llm_names)
        subagent_toolset = create_subagent_toolset(subagent_manager)
        tool_manager.add_toolset(subagent_toolset)

        subagent_manager.register_plugins()

    issue_manager = IssueManager(group_chat)
    agent_issue_toolset = create_issue_toolset(issue_manager)
    tool_manager.add_toolset(agent_issue_toolset)

    return agent


async def _create_llm_instances(
    llm_configs: list, group_chat: GroupChat
) -> list[LanguageModel]:
    """创建LLM实例列表

    Args:
        llm_configs: LLM配置列表
        group_chat: GroupChat实例，用于发送通知

    Returns:
        LLM实例列表
    """

    async def notification_callback(
        level: Literal["INFO", "WARNING", "ERROR"], content: str
    ) -> None:
        """发送通知到ui_log队列"""
        notice = CliRuntimeNotice(level=level, content=content)
        await group_chat.send_if_exists("ui_log", notice)

    llms = []
    for llm_config in llm_configs:
        llm_config_dict = llm_config.model_dump()
        llm = OpenAi(
            group_chat=group_chat,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config_dict.get("client_options", {}),
            chat_completion_kwargs=llm_config_dict.get("completion_options", {}),
            token_limit=llm_config_dict.get("token_limit"),
            compatibility=llm_config_dict.get("compatibility"),
        )
        llms.append(llm)
    return llms


async def _create_agent_context(
    llms: list[LanguageModel],
    llm_names: list[str],
    llm_name: str | None,
    agent_config: AgentConfig,
) -> AgentContext:
    """创建AgentConfig字典

    Args:
        llms: LLM实例列表
        llm_names: LLM名称列表
        llm_name: 指定的LLM名称
        tool_confirmation_config: 工具确认配置
        agent_config: Agent配置部分（可选）

    Returns:
        AgentConfig字典
    """

    compress_threshold: int | float = 0.8

    if agent_config:
        compress_threshold = agent_config.compress_threshold

    current_llm_index = 0
    if llm_name is not None:
        if llm_name in llm_names:
            current_llm_index = llm_names.index(llm_name)
        else:
            available_llms = ", ".join(llm_names)
            raise ValueError(
                f"LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"
            )

    agent_context: AgentContext = {
        "llms": llms,
        "llm_names": llm_names,
        "current_llm_index": current_llm_index,
        "compress_threshold": compress_threshold,
        "enable_directory_change_detection": (
            agent_config.enable_directory_change_detection if agent_config else False
        ),
    }
    return agent_context


async def _create_tool_manager(
    group_chat, config: ToolConfig, mcp_config: list[MCPConfig], mcp_basedir: Path
):
    """创建ToolManager实例"""
    from linhai.machine_control import MachineControl

    tool_manager = ToolManager(
        group_chat=group_chat,
        toolsets=[global_tools],
        config=config,
        mcp_config=mcp_config,
        mcp_basedir=mcp_basedir,
    )

    machine_control = MachineControl(group_chat)

    tool_manager.add_toolset(register_machine_control_tools(machine_control))

    return tool_manager, machine_control


async def _create_init_messages(
    group_chat: GroupChat,
    memory_file_path: Path | None = None,
    checklist_path: Path | None = None,
) -> list[Message]:
    """创建初始化消息列表

    Args:
        group_chat: GroupChat实例
        memory_file_path: 记忆文件路径（可选）
        checklist_path: 检查清单文件路径（可选）

    Returns:
        初始化消息列表
    """
    init_messages: list[Message] = [SystemMessage(group_chat)]

    user_global_memory = (
        Path(memory_file_path).absolute()
        if memory_file_path
        else Path("~/.config/linhai/LINHAI.md").expanduser()
    )
    init_messages.append(GlobalMemory(user_global_memory))

    if checklist_path:
        from .base import ChecklistMessage

        init_messages.append(ChecklistMessage(checklist_path))
        await group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO",
                content=f"已加载检查清单文件: {checklist_path}",
            ),
        )

    project_memory_filepaths = [
        Path("./LINHAI.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    for filepath in project_memory_filepaths:
        if filepath.exists():
            init_messages.append(GlobalMemory(filepath))

    return init_messages
