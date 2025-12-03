"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
import datetime
import logging
from typing import Literal

from linhai.config import AgentConfig, Config, MCPConfig, ToolConfig
from linhai.group_chat import GroupChat
from linhai.llm import LanguageModel, Message, OpenAi, SystemMessage
from linhai.prompt import DEFAULT_SYSTEM_PROMPT
from linhai.subagent import SubAgentManager
from linhai.subagent.clarification import ClarificationManager
from linhai.subagent.tools import create_subagent_toolset
from linhai.tool.base import global_tools
from linhai.tool.main import ToolManager
from linhai.tool.tools.terminal import terminal_toolset
from linhai.tool.tools.todolist import (
    TodolistManager,
    create_agent_todolist_toolset,
)
from linhai.utils import CliRuntimeNotice

from .base import AgentContext, GlobalMemory
from .clarification_tools import (
    create_clarification_toolset as create_agent_clarification_toolset,
)


async def create_agent_from_config(
    group_chat: GroupChat,
    config: Config,
    llm_name: str | None = None,
    config_basedir: Path | None = None,
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

    tool_manager = await _create_tool_manager(
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
        system_prompt=agent_context["system_prompt"],
        memory_file_path=memory_file_path,
    )

    agent = Agent(
        context=agent_context,
        group_chat=group_chat,
        init_messages=init_messages,
    )

    subagent_config = config.subagent
    if subagent_config and subagent_config.enable:
        subagent_manager = SubAgentManager(group_chat, subagent_config, llms, llm_names)
        subagent_toolset = create_subagent_toolset(subagent_manager)
        tool_manager.add_toolset(subagent_toolset)

        subagent_manager.register_plugins()

    clarification_manager = ClarificationManager(group_chat)
    agent_clarification_toolset = create_agent_clarification_toolset(
        clarification_manager
    )
    tool_manager.add_toolset(agent_clarification_toolset)

    return agent


async def _create_llm_instances(llm_configs: list, group_chat: GroupChat) -> list[LanguageModel]:
    """创建LLM实例列表

    Args:
        llm_configs: LLM配置列表
        group_chat: GroupChat实例，用于发送通知

    Returns:
        LLM实例列表
    """
    
    logger = logging.getLogger(__name__)
    
    async def notification_callback(level: Literal["INFO", "WARNING", "ERROR"], content: str) -> None:
        """发送通知到ui_log队列"""
        notice = CliRuntimeNotice(level=level, content=content)
        await group_chat.send_if_exists("ui_log", notice)
    
    llms = []
    for llm_config in llm_configs:
        llm_config_dict = llm_config.model_dump()
        llm = OpenAi(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config_dict.get("client_options", {}),
            chat_completion_kwargs=llm_config_dict.get("completion_options", {}),
            token_limit=llm_config_dict.get("token_limit"),
            compatibility=llm_config_dict.get("compatibility"),
            notification_callback=notification_callback,
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

    compress_threshold_hard: int | float = 0.8
    compress_threshold_soft: int | float = 0.5

    if agent_config:
        compress_threshold_hard = agent_config.compress_threshold_hard
        compress_threshold_soft = agent_config.compress_threshold_soft

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
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "llms": llms,
        "llm_names": llm_names,
        "current_llm_index": current_llm_index,
        "compress_threshold_hard": compress_threshold_hard,
        "compress_threshold_soft": compress_threshold_soft,
        "enable_directory_change_detection": (
            agent_config.enable_directory_change_detection if agent_config else False
        ),
    }
    return agent_context


async def _create_tool_manager(
    group_chat, config: ToolConfig, mcp_config: list[MCPConfig], mcp_basedir: Path
):
    """创建ToolManager实例"""
    tool_manager = ToolManager(
        group_chat=group_chat,
        toolsets=[global_tools, terminal_toolset],
        config=config,
        mcp_config=mcp_config,
        mcp_basedir=mcp_basedir,
    )
    return tool_manager


async def _create_init_messages(
    group_chat: GroupChat,
    system_prompt: str,
    memory_file_path: Path | None = None,
) -> list[Message]:
    """创建初始化消息列表

    Args:
        group_chat: GroupChat实例
        system_prompt: 系统提示语
        memory_file_path: 记忆文件路径（可选）

    Returns:
        初始化消息列表
    """
    init_messages: list[Message] = [
        SystemMessage(
            template=system_prompt,
            group_chat=group_chat,
        )
    ]

    user_global_memory = (
        memory_file_path.absolute()
        if memory_file_path
        else Path("~/.config/linhai/LINHAI.md").expanduser()
    )
    init_messages.append(GlobalMemory(user_global_memory))

    project_memory_filepaths = [
        Path("./LINHAI.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    for filepath in project_memory_filepaths:
        if filepath.exists():
            init_messages.append(GlobalMemory(filepath))

    return init_messages
