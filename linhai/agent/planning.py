from pathlib import Path
from typing import TYPE_CHECKING
from .messages import RuntimeMessage
from linhai import prompt
from ..prompt import INTRODUCTION_PLANNING_MODE, EXAMPLES_PLANNING_MODE

if TYPE_CHECKING:
    from .create import AgentBuildContext


class PlanningPromptMessage(RuntimeMessage):
    def __init__(self, planning_folder: Path):
        self.planning_folder = planning_folder
        self.status_file = planning_folder / "STATUS.md"
        self.todolist_file = planning_folder / "TODOLIST.md"
        self.design_file = planning_folder / "DESIGN.md"

        content = prompt.PLANNING_MODE_PROMPT.format(
            status_file=str(self.status_file),
            todolist_file=str(self.todolist_file),
            design_file=str(self.design_file),
        )

        super().__init__(content)

    def get_file_paths(self) -> dict[str, Path]:
        return {
            "status": self.status_file,
            "todolist": self.todolist_file,
            "design": self.design_file,
        }


def init_planning_folder(conversation_folder: Path) -> Path:
    """初始化规划文件夹，返回规划文件夹路径"""
    planning_folder = conversation_folder / "planning"
    planning_folder.mkdir(exist_ok=True)
    return planning_folder


def create_planning_files(planning_folder: Path) -> None:
    """创建规划所需的三个.md文件"""
    status_file = planning_folder / "STATUS.md"
    todolist_file = planning_folder / "TODOLIST.md"
    design_file = planning_folder / "DESIGN.md"

    if not status_file.exists():
        status_file.write_text(
            "当前任务: 未设置\n当前attempt: 1\n\n描述你的当前状态和下一步计划。\n"
        )
    if not todolist_file.exists():
        todolist_file.write_text("- [ ] 开始规划任务\n")
    if not design_file.exists():
        design_file.write_text("描述任务的设计思路。\n")


def setup_planning_for_agent(context: "AgentBuildContext") -> RuntimeMessage:
    """为agent设置规划模式，返回PlanningPromptMessage实例"""
    conversation_folder = context["registry"].get_member_typechecked(
        "conversation_folder", Path
    )
    if not conversation_folder:
        raise ValueError("无法获取对话文件夹路径")

    planning_folder = init_planning_folder(conversation_folder)
    create_planning_files(planning_folder)

    context["registry"].register_member("planning_folder", planning_folder)

    def register_system_message():
        from ..base import SystemMessage

        system_message = context["registry"].get_member_typechecked(
            "system_message", SystemMessage
        )
        system_message.add_introduction(
            "PLANNING",
            INTRODUCTION_PLANNING_MODE.format(
                status_file=str(planning_folder / "STATUS.md"),
                todolist_file=str(planning_folder / "TODOLIST.md"),
                design_file=str(planning_folder / "DESIGN.md"),
            ),
        )
        system_message.add_example("PLANNING", EXAMPLES_PLANNING_MODE)

    context["registry"].add_postinit(register_system_message)

    return PlanningPromptMessage(planning_folder)
