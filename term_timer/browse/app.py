"""Main browse application for term-timer."""
from typing import ClassVar

from textual.app import App
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.widgets import Footer
from textual.widgets import Header

from term_timer.browse.panels.detail import DetailPanel
from term_timer.browse.panels.sessions import SessionsPanel
from term_timer.browse.panels.solves import SolvesPanel

PanelType = SessionsPanel | SolvesPanel | DetailPanel


class BrowseApp(App[None]):
    """Interactive TUI for browsing solve sessions and details."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #top-panels {
        height: 50%;
    }

    #bottom-panel {
        height: 50%;
    }
    """

    BINDINGS: ClassVar[
        list[Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        Binding('q', 'quit', 'Quit', priority=True),
        Binding('tab', 'next_panel', 'Next Panel'),
        Binding('shift+tab', 'previous_panel', 'Previous Panel'),
        Binding('r', 'refresh', 'Refresh'),
    ]

    def __init__(self) -> None:
        """Initialize the browse app."""
        super().__init__()
        self.title = 'Term-Timer Browse'
        self.sub_title = 'Solve Sessions Browser'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the application layout.

        Yields:
            Widget components for the application layout.

        """
        yield Header()
        with Horizontal(id='top-panels'):
            yield SessionsPanel()
            yield SolvesPanel()
        with Vertical(id='bottom-panel'):
            yield DetailPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app when mounted."""
        # Focus on sessions panel by default
        sessions_panel = self.query_one(SessionsPanel)
        sessions_panel.focus()

    def on_sessions_panel_session_selected(
        self,
        event: SessionsPanel.SessionSelected,
    ) -> None:
        """Handle session selection from sessions panel."""
        solves_panel = self.query_one(SolvesPanel)
        solves_panel.load_session(event.cube_size, event.session_name)

        # Focus on solves panel after loading
        solves_panel.focus()

    def on_solves_panel_solve_selected(
        self,
        event: SolvesPanel.SolveSelected,
    ) -> None:
        """Handle solve selection from solves panel."""
        detail_panel = self.query_one(DetailPanel)
        detail_panel.display_solve(
            event.solve,
            event.solve_index,
            event.cube_size,
        )

        # Focus on detail panel after loading
        detail_panel.focus()

    def action_next_panel(self) -> None:
        """Focus next panel (Tab)."""
        focused = self.focused
        panels: list[PanelType] = [
            self.query_one(SessionsPanel),
            self.query_one(SolvesPanel),
            self.query_one(DetailPanel),
        ]

        if isinstance(focused, (SessionsPanel, SolvesPanel, DetailPanel)):
            current_index = panels.index(focused)
            next_index = (current_index + 1) % len(panels)
            panels[next_index].focus()
        else:
            panels[0].focus()

    def action_previous_panel(self) -> None:
        """Focus previous panel (Shift+Tab)."""
        focused = self.focused
        panels: list[PanelType] = [
            self.query_one(SessionsPanel),
            self.query_one(SolvesPanel),
            self.query_one(DetailPanel),
        ]

        if isinstance(focused, (SessionsPanel, SolvesPanel, DetailPanel)):
            current_index = panels.index(focused)
            previous_index = (current_index - 1) % len(panels)
            panels[previous_index].focus()
        else:
            panels[0].focus()

    def action_refresh(self) -> None:
        """Refresh the current view."""
        sessions_panel = self.query_one(SessionsPanel)
        sessions_panel.load_sessions()


async def run_browse() -> None:
    """Run the browse application."""
    app = BrowseApp()
    await app.run_async()
