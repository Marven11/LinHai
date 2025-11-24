"""SubAgent相关工具实现。"""

from linhai.tool.base import ToolSet, ToolArgInfo
from .main import SubAgentManager


def create_subagent_toolset(subagent_manager: SubAgentManager) -> ToolSet:
    """创建并返回SubAgent管理工具的ToolSet。"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="create_subagent",
        desc="创建并启动一个SubAgent执行任务",
        args={
            "agent_type": ToolArgInfo(
                desc="SubAgent类型，目前只支持'dummy'", type="str"
            ),
            "name": ToolArgInfo(desc="SubAgent名称", type="str"),
            "task_message": ToolArgInfo(desc="任务描述消息", type="str"),
        },
        required_args=["agent_type", "name", "task_message"],
    )
    async def create_subagent_tool(
        agent_type: str, name: str, task_message: str
    ) -> str:
        """创建并启动一个SubAgent。"""

        # 获取当前LLM实例
        from linhai.agent.main import Agent

        # 通过group_chat获取当前agent实例
        agent = subagent_manager.group_chat.get_members("agent", Agent)
        if not agent:
            return "错误: 无法获取Agent实例"

        return await subagent_manager.create_subagent(agent_type, name, task_message)

    @toolset.register_tool(
        name="check_subagent",
        desc="检查SubAgent的状态",
        args={"name": ToolArgInfo(desc="SubAgent名称", type="str")},
        required_args=["name"],
    )
    async def check_subagent_tool(name: str) -> str:
        """检查SubAgent状态。"""
        return await subagent_manager.check_subagent(name)

    return toolset
