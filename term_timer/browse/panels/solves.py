"""Solves panel for browsing solve list."""

import re

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

    BINDINGS = [  # noqa: RUF012
        ('t', 'sort_by_time', 'Sort by Time'),
        ('d', 'sort_by_date', 'Sort by Date'),
        ('f', 'sort_by_flag', 'Sort by Flag'),
    ]

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
        self.current_sorts: set[str] = set()

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the solves panel.

        Yields:
            Widget components for the solves panel layout.

        """
        yield Static('Solves')
        table: DataTable[str] = DataTable(cursor_type='row')
        table.add_column('#', key='#')
        table.add_column('Time', key='Time')
        table.add_column('Date', key='Date')
        table.add_column('Flag', key='Flag')
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

            # Add row with styled content, using solve_num as row key
            table.add_row(
                f'#{solve_num}',
                time_str,
                date_str,
                solve.flag,
                key=str(solve_num),
            )

    def sort_reverse_toggle(self, sort_type: str) -> bool:
        """
        Determine if sort should be reversed (toggle on repeated sorts).

        Args:
            sort_type: The type of sort being performed.

        Returns:
            True if sort should be reversed, False otherwise.

        """
        reverse = sort_type in self.current_sorts
        if reverse:
            self.current_sorts.remove(sort_type)
        else:
            self.current_sorts.add(sort_type)
        return reverse

    def action_sort_by_time(self) -> None:
        """Sort table by solve time."""
        if not self.solves:
            return
        table = self.query_one(DataTable)
        # Need custom key to sort by actual time value, not formatted string
        table.sort(
            'Time',
            key=self._extract_time_from_display,
            reverse=self.sort_reverse_toggle('time'),
        )

    def action_sort_by_date(self) -> None:
        """Sort table by solve date."""
        if not self.solves:
            return
        table = self.query_one(DataTable)
        table.sort('Date', reverse=self.sort_reverse_toggle('date'))

    def action_sort_by_flag(self) -> None:
        """Sort table by solve flag."""
        if not self.solves:
            return
        table = self.query_one(DataTable)
        table.sort('Flag', reverse=self.sort_reverse_toggle('flag'))

    @staticmethod
    def _extract_time_from_display(time_str: str) -> float:
        """
        Extract numeric time value from formatted display string.

        Args:
            time_str: Formatted time string (may include Rich markup).

        Returns:
            Numeric time value in seconds.

        """
        # Remove Rich markup tags
        clean_str = re.sub(r'\[.*?\]', '', str(time_str))
        # Parse time - format can be "1:23.45" or "23.45"
        parts = clean_str.split(':')
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        return float(parts[0])

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected,
    ) -> None:
        """Handle row selection."""
        if not self.solves or self.current_cube_size is None:
            return

        # Get solve_num from row key (1-based index)
        row_key_value = event.row_key.value
        if row_key_value is None:
            return
        solve_num = int(row_key_value)
        solve_index = solve_num - 1  # Convert to 0-based index
        solve = self.solves[solve_index]

        self.post_message(
            self.SolveSelected(
                solve=solve,
                solve_index=solve_num,
                cube_size=self.current_cube_size,
            ),
        )
