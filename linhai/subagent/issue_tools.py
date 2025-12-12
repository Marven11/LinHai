"""SubAgent的issue相关工具。"""

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.subagent.issue import IssueManager, IssueError
from linhai.subagent.main import SubAgent
from linhai.utils import generate_id


def create_issue_toolset(issue_manager: IssueManager, subagent: SubAgent) -> ToolSet:
    """创建并返回SubAgent的issue管理工具集。

    Args:
        issue_manager: IssueManager实例
        subagent: SubAgent实例，工具可以直接访问
    """
    toolset = ToolSet()
    subagent_name = subagent.name

    @toolset.register_tool(
        name="request_issue",
        desc="向Agent请求issue，等待Agent回复",
        args={"content": ToolArgInfo(desc="需要issue的内容", type="str")},
        required_args=["content"],
    )
    async def request_issue(content: str) -> str:
        """向Agent请求issue并等待回复。"""
        issue_id = generate_id("issue")

        await issue_manager.request_issue(issue_id, content, subagent_name)

        if issue_manager.is_issue_limit_exceeded(subagent_name):
            subagent.exit("已达到issue限额，SubAgent退出。")
            return f"已创建issue {issue_id}，SubAgent因达到限额而退出。"

        answer = await issue_manager.wait_for_response(issue_id)
        return f"Agent回复issue: {answer}"

    return toolset
