"""Planning tab widget for displaying planning mode files."""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Markdown, Static

from linhai.registry import Registry

FILE_NAMES = ["STATUS.md", "TODOLIST.md", "DESIGN.md"]

FILE_IDS = {name: name.lower().replace(".", "-") for name in FILE_NAMES}


class PlanningTabWidget(Static):
    """Widget for displaying planning files with collapsible sections."""

    DEFAULT_CSS = """
    PlanningTabWidget {
        width: 100%;
        height: 100%;
    }

    PlanningTabWidget VerticalScroll {
        padding-right: 1;
        scrollbar-size-vertical: 1;
    }
    """

    def __init__(self, registry: Registry) -> None:
        super().__init__()
        self.registry = registry
        self.refresh_interval = 0.5
        self.planning_folder: Optional[Path] = None
        self._file_contents: dict[str, str] = {name: "" for name in FILE_NAMES}

    def _get_planning_folder(self) -> Optional[Path]:
        if self.planning_folder is not None:
            return self.planning_folder

        if not self.registry.has_member("planning_folder"):
            return None

        self.planning_folder = self.registry.get_member_typechecked(
            "planning_folder", Path
        )
        return self.planning_folder

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            for name in FILE_NAMES:
                with Collapsible(
                    title=name,
                    id=f"planning-collapsible-{FILE_IDS[name]}",
                    collapsed=False,
                ):
                    yield Markdown(id=f"planning-content-{FILE_IDS[name]}")

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_display)
        self.update_display()

    def update_display(self) -> None:
        planning_folder = self._get_planning_folder()
        if planning_folder is None:
            return

        for name in FILE_NAMES:
            file_path = planning_folder / name
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            if content == self._file_contents[name]:
                continue

            self._file_contents[name] = content
            markdown_widget = self.query_one(
                f"#planning-content-{FILE_IDS[name]}", Markdown
            )
            markdown_widget.update(content)
