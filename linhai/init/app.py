"""Init TUI application for LinHai configuration."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Header, Footer
from textual.reactive import reactive

from .widgets import ConfigForm, ButtonBar
from .config_writer import write_llm_config, write_agents_md


class InitApp(App):
    """TUI application for initializing LinHai configuration."""

    CSS = """
Screen {
    align: center middle;
}

#main-container {
    width: 70;
    height: 85%;
    border: solid grey;
    padding: 2 3;
}

#title {
    text-align: center;
    text-style: bold;
    margin-bottom: 1;
}

#subtitle {
    text-align: center;
    margin-bottom: 2;
}

.input-label {
    margin-top: 1;
}

.config-input {
    width: 100%;
    height: auto;
    min-height: 3;
    margin-top: 1;
}

.input-error {
    margin-top: 1;
}

#button-bar {
    width: 100%;
    height: 3;
    align: center middle;
    margin-top: 2;
}

#status-message {
    text-align: center;
    margin-top: 2;
    padding: 1;
}
"""

    status_message = reactive("")
    status_class = reactive("status-info")

    def __init__(self, config_path: Path | None = None):
        super().__init__()
        from linhai.config import get_default_config_path

        self.config_path = config_path or get_default_config_path()

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=False)

        with VerticalScroll(id="main-container"):
            yield Static("LinHai 初始化配置", id="title")
            yield Static("配置你的第一个LLM", id="subtitle")

            yield ConfigForm()
            yield ButtonBar(id="button-bar")

            yield Static("", id="status-message", classes="status-info")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize status display after mount."""
        status_widget = self.query_one("#status-message", Static)
        status_widget.update(self.status_message)
        status_widget.classes = self.status_class

    def watch_status_message(self, message: str) -> None:
        """Watch for status message changes."""
        status_widget = self.query_one("#status-message", Static)
        if status_widget.is_mounted:
            status_widget.update(message)

    def watch_status_class(self, class_name: str) -> None:
        """Watch for status class changes."""
        status_widget = self.query_one("#status-message", Static)
        if status_widget.is_mounted:
            status_widget.classes = class_name

    def validate_form(self, values: dict[str, str]) -> list[tuple[str, str]]:
        """Validate form values.

        Returns:
            List of (field_name, error_message) tuples.
        """
        errors = []

        if not values["name"].strip():
            errors.append(("name", "LLM名称不能为空"))

        if not values["base_url"].strip():
            errors.append(("base_url", "Base URL不能为空"))
        elif not values["base_url"].startswith(("http://", "https://")):
            errors.append(("base_url", "Base URL必须以http://或https://开头"))

        if not values["api_key"].strip():
            errors.append(("api_key", "API Key不能为空"))

        if not values["model"].strip():
            errors.append(("model", "Model不能为空"))

        return errors

    async def on_button_pressed(self, event) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.exit(0)

        elif button_id == "btn-save":
            form = self.query_one(ConfigForm)
            values = form.get_values()

            form.clear_errors()

            errors = self.validate_form(values)
            if errors:
                for field, message in errors:
                    form.set_error(field, message)
                self.status_message = "错误: 请修正表单中的错误"
                self.status_class = "status-error"
                return

            write_llm_config(
                name=values["name"],
                base_url=values["base_url"],
                api_key=values["api_key"],
                model=values["model"],
                config_path=self.config_path,
                overwrite=True,
            )
            cat_mode = form.get_cat_mode()
            write_agents_md(self.config_path.parent, cat_mode=cat_mode)
            self.status_message = f"配置已保存到 {self.config_path}"
            self.status_class = "status-success"
            self.exit(0)
