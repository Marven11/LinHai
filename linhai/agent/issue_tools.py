"""Agent的issue相关工具。"""

from datetime import datetime
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.subagent.issue import IssueManager


def create_issue_toolset(
    issue_manager: IssueManager,
) -> ToolSet:
    """创建并返回Agent的issue管理工具集。"""
    toolset = ToolSet()
    
    @toolset.register_tool(
        name="respond_issue",
        desc="回复SubAgent的issue，这个工具可以安全地和其他工具一起调用",
        args={
            "issue_id": ToolArgInfo(desc="issue的ID", type="str"),
            "answer": ToolArgInfo(desc="对issue的回答", type="str"),
        },
        required_args=["issue_id", "answer"],
    )
    def respond_issue(issue_id: str, answer: str) -> str:
        """回复SubAgent的issue。"""
        return issue_manager.respond_issue(issue_id, answer)
    
    @toolset.register_tool(
        name="list_issues",
        desc="列出所有未解答的issue及其可回答时间",
        args={},
        required_args=[],
    )
    def list_issues() -> str:
        """列出所有未解答的issue。"""
        unanswered = issue_manager.get_unanswered_issues()
        
        if not unanswered:
            return "当前没有未解答的issue。"
        
        result = "未解答的issue:\n"
        for issue in unanswered:
            result += f"\nID: {issue['id']}\n"
            result += f"来自: {issue['from_subagent']}\n"
            result += f"内容: {issue['content']}\n"
            time_since_creation = datetime.now() - issue["created_at"]
            time_remaining = issue["min_response_interval"] - time_since_creation
            if time_remaining.total_seconds() > 0:
                result += f"可回答时间: {time_remaining.total_seconds():.0f}秒后\n"
            else:
                result += "可回答时间: 现在\n"
            result += "-" * 3
        
        return result
    
    return toolset