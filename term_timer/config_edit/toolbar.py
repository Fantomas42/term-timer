"""Toolbar for config editor with save/reset/cancel buttons."""
from typing import Any

import rtoml
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button
from textual.widgets import Static

from term_timer.config_edit.sections import BluetoothSection
from term_timer.config_edit.sections import ConfigData
from term_timer.config_edit.sections import CubeSection
from term_timer.config_edit.sections import DisplaySection
from term_timer.config_edit.sections import PublisherSection
from term_timer.config_edit.sections import ServerSection
from term_timer.config_edit.sections import StatisticsSection
from term_timer.config_edit.sections import TimerSection
from term_timer.config_edit.sections import TrainerSection
from term_timer.constants import CONFIG_FILE


class ConfigToolbar(Widget):
    """Toolbar with save, reset, and cancel buttons."""

    DEFAULT_CSS = """
    ConfigToolbar {
        height: auto;
        background: $panel;
        border-top: solid $primary;
        padding: 1 2;
    }

    ConfigToolbar Horizontal {
        height: auto;
        align: center middle;
    }

    ConfigToolbar Button {
        margin: 0 1;
    }

    ConfigToolbar .status-message {
        margin-left: 2;
        text-style: italic;
        color: $text-muted;
    }
    """

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the toolbar.

        Yields:
            Textual widgets for the toolbar (buttons and status message).

        """
        with Horizontal():
            yield Button('Save', id='save-btn', variant='primary')
            yield Button('Reset', id='reset-btn', variant='default')
            yield Button('Cancel', id='cancel-btn', variant='warning')
            yield Static('', classes='status-message')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == 'save-btn':
            self.save_config()
        elif event.button.id == 'reset-btn':
            self.reset_config()
        elif event.button.id == 'cancel-btn':
            self.confirm_exit()

    def save_config(self) -> None:
        """Save all configuration sections to file."""
        app = self.app
        if not hasattr(app, 'mark_saved'):
            return

        sections = [
            TimerSection,
            CubeSection,
            TrainerSection,
            DisplaySection,
            BluetoothSection,
            StatisticsSection,
            ServerSection,
            PublisherSection,
        ]

        config_data: ConfigData = {}
        for section_class in sections:
            section = app.query_one(section_class)
            config_data.update(section.get_config_data())

        self.write_config_file(config_data)
        app.mark_saved()

        status = self.query_one('.status-message', Static)
        status.update('Configuration saved successfully!')
        self.set_timer(3, lambda: status.update(''))

    @staticmethod
    def write_config_file(
        config_data: ConfigData,
    ) -> None:
        """
        Write configuration data to TOML file.

        The editor only knows about a handful of sections, so the edited
        ones are merged over the file instead of replacing it, leaving
        whatever it does not handle untouched, like the [ui] theme.

        Merging stays shallow on purpose: a key the editor owns, such as
        the cube table, is replaced as a whole so that removing a cube in
        the interface really removes it from the file.
        """
        config: dict[str, Any] = {}
        if CONFIG_FILE.exists():
            config = rtoml.load(CONFIG_FILE)

        for section, values in config_data.items():
            current = config.get(section)
            if isinstance(current, dict):
                current.update(values)
            else:
                config[section] = values

        rtoml.dump(config, CONFIG_FILE)

    def reset_config(self) -> None:
        """Reset all sections to current saved values."""
        app = self.app
        if not hasattr(app, 'mark_saved'):
            return

        sections = [
            TimerSection,
            CubeSection,
            TrainerSection,
            DisplaySection,
            BluetoothSection,
            StatisticsSection,
            ServerSection,
            PublisherSection,
        ]

        for section_class in sections:
            section = app.query_one(section_class)
            section.load_config()

        app.mark_saved()

        status = self.query_one('.status-message', Static)
        status.update('Configuration reset to saved values.')
        self.set_timer(3, lambda: status.update(''))

    def confirm_exit(self) -> None:
        """Confirm exit if there are unsaved changes."""
        self.app.exit()
