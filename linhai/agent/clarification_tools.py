"""Agent的澄清相关工具。"""

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.subagent.clarification import ClarificationManager


def create_clarification_toolset(
    clarification_manager: ClarificationManager,
) -> ToolSet:
    """创建并返回Agent的澄清管理工具集。"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="respond_clarification",
        desc="回复SubAgent的澄清问题，这个工具可以安全地和其他工具一起调用",
        args={
            "clarification_id": ToolArgInfo(desc="澄清问题的ID", type="str"),
            "answer": ToolArgInfo(desc="对澄清问题的回答", type="str"),
        },
        required_args=["clarification_id", "answer"],
    )
    def respond_clarification(clarification_id: str, answer: str) -> str:
        """回复SubAgent的澄清问题。"""
        try:
            clarification_manager.respond_clarification(clarification_id, answer)
            return f"成功回复澄清 {clarification_id}"
        except ValueError as e:
            return f"错误: {str(e)}"

    @toolset.register_tool(
        name="list_clarifications",
        desc="列出所有未解答的澄清问题",
        args={},
        required_args=[],
    )
    def list_clarifications() -> str:
        """列出所有未解答的澄清问题。"""
        unanswered = clarification_manager.get_unanswered_clarifications()

        if not unanswered:
            return "当前没有未解答的澄清问题。"

        result = "未解答的澄清问题:\n"
        for clarification in unanswered:
            result += f"\nID: {clarification['id']}\n"
            result += f"来自: {clarification['from_subagent']}\n"
            result += f"问题: {clarification['question']}\n"
            result += "-" * 3

        return result

    return toolset
