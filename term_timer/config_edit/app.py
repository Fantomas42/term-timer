"""Main configuration editor application."""
from typing import ClassVar

from textual.app import App
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer
from textual.widgets import Header
from textual.widgets import TabbedContent
from textual.widgets import TabPane

from term_timer.config_edit.sections import BluetoothSection
from term_timer.config_edit.sections import CubeSection
from term_timer.config_edit.sections import DisplaySection
from term_timer.config_edit.sections import ServerSection
from term_timer.config_edit.sections import StatisticsSection
from term_timer.config_edit.sections import TimerSection
from term_timer.config_edit.sections import TrainerSection
from term_timer.config_edit.toolbar import ConfigToolbar


class ConfigEditApp(App[None]):
    """Interactive TUI for editing term-timer configuration."""

    CSS = """
    Screen {
        layout: vertical;
    }

    TabbedContent {
        height: 1fr;
    }

    ConfigToolbar {
        height: auto;
        dock: bottom;
    }
    """

    BINDINGS: ClassVar[
        list[Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        Binding('q', 'quit', 'Quit', priority=True),
        Binding('ctrl+s', 'save', 'Save'),
        Binding('ctrl+r', 'reset', 'Reset'),
        Binding('escape', 'cancel', 'Cancel'),
    ]

    def __init__(self) -> None:
        """Initialize the config editor app."""
        super().__init__()
        self.title = 'Term-Timer Configuration'
        self.sub_title = 'Edit application settings'
        self.has_unsaved_changes = False

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the application layout.

        Yields:
            Widget components for the application layout.

        """
        yield Header()
        with TabbedContent():
            with TabPane('Timer', id='timer-tab'):
                yield TimerSection()
            with TabPane('Cube', id='cube-tab'):
                yield CubeSection()
            with TabPane('Trainer', id='trainer-tab'):
                yield TrainerSection()
            with TabPane('Display', id='display-tab'):
                yield DisplaySection()
            with TabPane('Bluetooth', id='bluetooth-tab'):
                yield BluetoothSection()
            with TabPane('Statistics', id='statistics-tab'):
                yield StatisticsSection()
            with TabPane('Server', id='server-tab'):
                yield ServerSection()
        yield ConfigToolbar()
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app when mounted."""
        self.update_subtitle()

    def update_subtitle(self) -> None:
        """Update subtitle to show save status."""
        if self.has_unsaved_changes:
            self.sub_title = 'Edit application settings (unsaved changes)'
        else:
            self.sub_title = 'Edit application settings'

    def mark_modified(self) -> None:
        """Mark configuration as modified."""
        self.has_unsaved_changes = True
        self.update_subtitle()

    def mark_saved(self) -> None:
        """Mark configuration as saved."""
        self.has_unsaved_changes = False
        self.update_subtitle()

    def action_save(self) -> None:
        """Save configuration changes."""
        toolbar = self.query_one(ConfigToolbar)
        toolbar.save_config()

    def action_reset(self) -> None:
        """Reset all configuration to current saved values."""
        toolbar = self.query_one(ConfigToolbar)
        toolbar.reset_config()

    def action_cancel(self) -> None:
        """Cancel and exit without saving."""
        if self.has_unsaved_changes:
            toolbar = self.query_one(ConfigToolbar)
            toolbar.confirm_exit()
        else:
            self.exit()


async def run_config_edit() -> None:
    """Run the configuration editor application."""
    app = ConfigEditApp()
    await app.run_async()
