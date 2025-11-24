"""Agent创建模块，负责初始化Agent实例和相关组件。"""

from pathlib import Path
import datetime

from linhai.group_chat import GroupChat
from linhai.llm import Message, SystemMessage, LanguageModel, OpenAi
from linhai.config import load_config, ToolConfig, MCPConfig, AgentConfig
from linhai.tool.main import ToolManager
from linhai.tool.tools.terminal import terminal_toolset
from linhai.tool.base import global_tools
from linhai.prompt import DEFAULT_SYSTEM_PROMPT
from .base import GlobalMemory, AgentContext
from linhai.subagent.tools import create_subagent_toolset
from linhai.subagent import SubAgentManager
from linhai.clarification import ClarificationManager
from .clarification_tools import create_clarification_toolset as create_agent_clarification_toolset


async def create_agent(
    group_chat: GroupChat,
    config_path: Path,
    llm_name: str | None = None,
):
    """创建Agent实例

    Args:
        group_chat: GroupChat实例
        config_path: 配置文件路径
        llm_name: 指定的LLM名称（可选）

    Returns:
        Agent实例
    """
    from .main import Agent  # 避免循环导入
    
    config = load_config(config_path)

    # 创建LLM实例
    llms = await _create_llm_instances(config.llm)

    # 解析tool_confirmation配置
    tool_confirmation_config = {}
    if config.agent and config.agent.tool_confirmation:
        tool_confirmation_config = config.agent.tool_confirmation

    # 创建AgentConfig
    llm_names = [llm_config.name for llm_config in config.llm]
    agent_config = config.agent if config.agent else AgentConfig()
    agent_context = await _create_agent_context(
        llms=llms,
        llm_names=llm_names,
        llm_name=llm_name,
        tool_confirmation_config=tool_confirmation_config,
        agent_config=agent_config,
    )

    # 创建ToolManager
    tool_config = config.tools if config.tools else ToolConfig()
    tool_manager = await _create_tool_manager(group_chat, tool_config, agent_config.mcp, mcp_basedir=config_path.parent)

    # 获取subagent配置
    subagent_config = config.subagent if config.subagent else None

    # 创建SubAgentManager并注册subagent工具
    subagent_manager = SubAgentManager(group_chat, subagent_config, llms, llm_names)
    subagent_toolset = create_subagent_toolset(subagent_manager)
    tool_manager.add_toolset(subagent_toolset)

    # 创建初始化消息
    memory_file_path = (config_path.parent / config.memory.file_path) if config.memory else None
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

    # 创建ClarificationManager并注册澄清工具（在Agent之后，因为AgentMessage在Agent的__init__中注册）
    clarification_manager = ClarificationManager(group_chat)
    agent_clarification_toolset = create_agent_clarification_toolset(clarification_manager)
    tool_manager.add_toolset(agent_clarification_toolset)

    return agent


async def _create_llm_instances(llm_configs: list) -> list[LanguageModel]:
    """创建LLM实例列表

    Args:
        llm_configs: LLM配置列表

    Returns:
        LLM实例列表
    """
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
        )
        llms.append(llm)
    return llms


async def _create_agent_context(
    llms: list[LanguageModel],
    llm_names: list[str],
    llm_name: str | None,
    tool_confirmation_config: dict,
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
    # 设置压缩阈值（存储原始配置值，将在运行时根据当前LLM动态计算）
    compress_threshold_hard: int | float = 0.8  # 默认硬阈值比例
    compress_threshold_soft: int | float = 0.5  # 默认软阈值比例

    if agent_config:
        # 存储原始配置值，不转换为绝对token数
        compress_threshold_hard = agent_config.compress_threshold_hard
        compress_threshold_soft = agent_config.compress_threshold_soft

    # 处理llm_name参数
    current_llm_index = 0  # 默认使用第一个LLM
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
        "tool_confirmation": tool_confirmation_config,
        "enable_directory_change_detection": agent_config.enable_directory_change_detection if agent_config else False,
    }
    return agent_context


async def _create_tool_manager(group_chat, config: ToolConfig, mcp_config: list[MCPConfig], mcp_basedir: Path):
    """创建ToolManager实例"""
    tool_manager = ToolManager(
        group_chat=group_chat, toolsets=[global_tools, terminal_toolset], config=config, mcp_config=mcp_config, mcp_basedir=mcp_basedir
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
            current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            group_chat=group_chat,
        )
    ]

    user_global_memory = memory_file_path.absolute() if memory_file_path else Path("~/.config/linhai/LINHAI.md").expanduser()
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