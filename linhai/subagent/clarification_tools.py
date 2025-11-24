"""SubAgent的澄清相关工具。"""

import uuid
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.clarification import ClarificationManager
from linhai.utils import CliRuntimeNotice, generate_id


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

        # 添加澄清到管理器
        await clarification_manager.add_clarification(
            clarification_id, question, subagent_name
        )

        await clarification_manager.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"SubAgent添加了澄清请求: {question}"
            ),
        )

        # 等待Agent回复
        answer = await clarification_manager.wait_for_response(clarification_id)

        return f"Agent回复澄清: {answer}"

    return toolset
