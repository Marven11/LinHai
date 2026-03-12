"""Custom widgets for LinHai init TUI."""

from textual.widgets import Input, Static, Button
from textual.containers import Vertical, Horizontal


class LabeledInput(Vertical):
    """A labeled input widget."""

    def __init__(
        self,
        label: str,
        placeholder: str = "",
        password: bool = False,
        value: str = "",
        id: str | None = None,  # pylint: disable=redefined-builtin
    ):
        super().__init__(id=id)
        self.label_text = label
        self.placeholder = placeholder
        self.password = password
        self.default_value = value

    def compose(self):
        """Compose the widget."""
        yield Static(self.label_text, classes="input-label")
        yield Input(
            placeholder=self.placeholder,
            password=self.password,
            value=self.default_value,
            classes="config-input",
        )
        yield Static("", classes="input-error", id=f"{self.id}-error")

    @property
    def value(self) -> str:
        """Get the input value."""
        input_widget = self.query_one(Input)
        return input_widget.value

    def set_error(self, message: str | None) -> None:
        """Set or clear error message."""
        error_widget = self.query_one(f"#{self.id}-error", Static)

        if message:
            error_widget.update(message)
            error_widget.styles.display = "block"
        else:
            error_widget.update("")
            error_widget.styles.display = "none"


class ConfigForm(Static):
    """Configuration form widget."""

    def compose(self):
        """Compose the form."""
        with Vertical(classes="form-container"):
            yield LabeledInput(
                "LLM Name:",
                placeholder="e.g., default",
                value="default",
                id="input-name",
            )
            yield LabeledInput(
                "Base URL:",
                placeholder="e.g., https://api.openai.com/v1",
                value="https://api.openai.com/v1",
                id="input-base-url",
            )
            yield LabeledInput(
                "API Key:",
                placeholder="Your API key",
                password=True,
                id="input-api-key",
            )
            yield LabeledInput(
                "Model:",
                placeholder="e.g., gpt-4o-mini",
                value="gpt-4o-mini",
                id="input-model",
            )

    def get_values(self) -> dict[str, str]:
        """Get all form values."""
        return {
            "name": self.query_one("#input-name", LabeledInput).value,
            "base_url": self.query_one("#input-base-url", LabeledInput).value,
            "api_key": self.query_one("#input-api-key", LabeledInput).value,
            "model": self.query_one("#input-model", LabeledInput).value,
        }

    def set_error(self, field: str, message: str) -> None:
        """Set error message for a field."""
        field_id = f"input-{field.replace('_', '-')}"
        input_widget = self.query_one(f"#{field_id}", LabeledInput)
        input_widget.set_error(message)

    def clear_errors(self) -> None:
        """Clear all error messages."""
        for labeled_input in self.query(LabeledInput):
            labeled_input.set_error(None)


class ButtonBar(Horizontal):
    """Button bar widget."""

    def compose(self):
        """Compose the button bar."""
        yield Button("Save Configuration", variant="primary", id="btn-save")
        yield Button("Cancel", id="btn-cancel")
