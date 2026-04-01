"""Tests for init app using Textual's official testing approach with run_test() and Pilot."""

import unittest

from textual.widgets import Button, Static, Checkbox

from linhai.init.app import InitApp
from linhai.init.widgets import ButtonBar, LabeledInput


class TestInitAppWithPilot(unittest.IsolatedAsyncioTestCase):
    """Tests for InitApp using Textual's Pilot."""

    async def test_button_bar_mounted(self):
        """Test that ButtonBar is mounted in the app."""
        app = InitApp()
        async with app.run_test() as pilot:
            button_bar = pilot.app.query_one("#button-bar", ButtonBar)
            self.assertIsNotNone(button_bar)

    async def test_buttons_exist(self):
        """Test that Save and Cancel buttons exist."""
        app = InitApp()
        async with app.run_test() as pilot:
            save_btn = pilot.app.query_one("#btn-save", Button)
            cancel_btn = pilot.app.query_one("#btn-cancel", Button)

            self.assertIsNotNone(save_btn)
            self.assertIsNotNone(cancel_btn)

            self.assertIn("Save", str(save_btn.label))
            self.assertIn("Cancel", str(cancel_btn.label))

    async def test_checkbox_exists(self):
        """Test that cat mode checkbox exists."""
        app = InitApp()
        async with app.run_test() as pilot:
            checkbox = pilot.app.query_one("#checkbox-cat-mode", Checkbox)
            self.assertIsNotNone(checkbox)
            self.assertFalse(checkbox.value)

    async def test_save_button_triggers_validation(self):
        """Test that clicking Save button triggers form validation."""
        app = InitApp()
        async with app.run_test(size=(120, 40)) as pilot:
            # Clear all input fields to trigger validation errors
            name_input = pilot.app.query_one("#input-name", LabeledInput)
            base_url_input = pilot.app.query_one("#input-base-url", LabeledInput)
            api_key_input = pilot.app.query_one("#input-api-key", LabeledInput)
            model_input = pilot.app.query_one("#input-model", LabeledInput)

            # Set empty values to trigger validation
            name_input.query_one("Input").value = ""
            base_url_input.query_one("Input").value = ""
            api_key_input.query_one("Input").value = ""
            model_input.query_one("Input").value = ""

            # Focus the save button and press enter
            save_button = pilot.app.query_one("#btn-save", Button)
            save_button.focus()
            await pilot.press("enter")

            # Wait for UI to update
            await pilot.pause()

            # Verify that the form has been validated by checking status message
            status_widget = pilot.app.query_one("#status-message", Static)
            # Get content from Static widget - use the content property
            status_text = (
                str(status_widget.content)
                if hasattr(status_widget, "content")
                else str(status_widget)
            )

            # The status message should indicate there's an error
            self.assertIn("错误", status_text, "Expected error message in status")


class TestInitAppExistence(unittest.TestCase):
    """Basic existence tests for InitApp."""

    def test_app_class_exists(self):
        """Test that InitApp class exists."""
        self.assertTrue(callable(InitApp))

    def test_button_bar_class_exists(self):
        """Test that ButtonBar class exists."""
        self.assertTrue(callable(ButtonBar))


if __name__ == "__main__":
    unittest.main()
