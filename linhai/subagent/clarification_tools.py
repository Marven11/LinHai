"""SubAgent的澄清相关工具。"""

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.clarification import ClarificationManager
from linhai.utils import generate_id


def create_clarification_toolset(
    clarification_manager: ClarificationManager, subagent_name: str
) -> ToolSet:
    """创建并返回SubAgent的澄清管理工具集。"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="request_clarification",
        desc="向Agent请求澄清，等待Agent回复",
        args={"question": ToolArgInfo(desc="需要澄清的问题", type="str")},
        required_args=["question"],
    )
    async def request_clarification(question: str) -> str:
        """向Agent请求澄清并等待回复。"""
        clarification_id = generate_id("clarification")

        await clarification_manager.request_clarification(
            clarification_id, question, subagent_name
        )

        answer = await clarification_manager.wait_for_response(clarification_id)

        return f"Agent回复澄清: {answer}"

    return toolset
