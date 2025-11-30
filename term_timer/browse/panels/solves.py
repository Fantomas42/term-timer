"""Solves panel for browsing solve list."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import DataTable
from textual.widgets import Static

from term_timer.formatter import format_time
from term_timer.in_out import load_solves
from term_timer.solve import Solve
from term_timer.stats import Statistics


class SolvesPanel(VerticalScroll):
    """Panel displaying list of solves for a session."""

    DEFAULT_CSS = """
    SolvesPanel {
        width: 2fr;
        border-right: solid $primary;
    }

    SolvesPanel > Static {
        background: $boost;
        padding: 1;
        text-style: bold;
    }

    SolvesPanel DataTable {
        height: 1fr;
    }
    """

    class SolveSelected(Message):
        """Message sent when a solve is selected."""

        def __init__(
            self,
            solve: Solve,
            solve_index: int,
            cube_size: int,
        ) -> None:
            """Initialize message with solve info."""
            self.solve = solve
            self.solve_index = solve_index
            self.cube_size = cube_size
            super().__init__()

    def __init__(self) -> None:
        """Initialize the solves panel."""
        super().__init__()
        self.current_cube_size: int | None = None
        self.current_session: str | None = None
        self.solves: list[Solve] = []

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the solves panel.

        Yields:
            Widget components for the solves panel layout.

        """
        yield Static('Solves')
        table: DataTable[str] = DataTable(cursor_type='row')
        table.add_columns('#', 'Time', 'Date', 'Flag')
        yield table

    def load_session(self, cube_size: int, session_name: str) -> None:
        """
        Load solves for a specific session.

        Args:
            cube_size: Cube dimension (e.g., 3 for 3x3x3).
            session_name: Name of the session to load.

        """
        self.current_cube_size = cube_size
        self.current_session = session_name

        # Load solves
        self.solves = load_solves(cube_size, session_name)

        # Update header
        header = self.query_one(Static)
        header.update(
            f'Solves: {cube_size}x{cube_size}x{cube_size} - {session_name} '
            f'({len(self.solves)} solves)',
        )

        # Update table
        table = self.query_one(DataTable)
        table.clear()

        if not self.solves:
            return

        # Calculate best and worst for highlighting
        stats = Statistics(self.solves)
        best_time = stats.best
        worst_time = stats.worst

        # Add rows in reverse order (newest first)
        for i, solve in enumerate(reversed(self.solves)):
            solve_num = len(self.solves) - i
            time_str = format_time(solve.time)
            date_str = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

            # Apply styling for best/worst times using Rich markup
            if solve.time == best_time:
                time_str = f'[green]{time_str}[/green]'
            elif solve.time == worst_time:
                time_str = f'[red]{time_str}[/red]'

            # Add row with styled content
            table.add_row(
                f'#{solve_num}',
                time_str,
                date_str,
                solve.flag,
            )

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected,
    ) -> None:
        """Handle row selection."""
        if not self.solves or self.current_cube_size is None:
            return

        # Get row index (accounting for reverse order)
        row_index = event.cursor_row
        solve_index = len(self.solves) - row_index - 1
        solve = self.solves[solve_index]

        self.post_message(
            self.SolveSelected(
                solve=solve,
                solve_index=solve_index + 1,
                cube_size=self.current_cube_size,
            ),
        )
