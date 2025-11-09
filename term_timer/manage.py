"""Solve and session management utilities for editing and deleting solves."""

from rich import box
from rich.table import Table

from term_timer.constants import CUBE_SIZES
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import Statistics


class SolveManager:
    """
    Manages individual solve operations including updates and deletions.

    This class handles loading, modifying, and persisting individual solve
    records within a specific cube size and session. It provides methods
    for retrieving, updating flags, and deleting solves with user
    confirmation.
    """

    def __init__(self, cube: int, session: str, solve_id: int) -> None:
        """
        Initialize the SolveManager with cube, session, and solve ID.

        Args:
            cube: The cube size (e.g., 3 for 3x3x3).
            session: The name of the session containing the solve.
            solve_id: The one-based solve number to manage.

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id

        self.solve_index = solve_id - 1
        self.stack = load_solves(cube, session)

        self.solve = self.get_solve()

    def get_solve(self) -> Solve | None:
        """
        Retrieve the solve at the specified index from the solve stack.

        Returns:
            The solve object if found, None if the solve ID is invalid.

        """
        try:
            solve = self.stack[self.solve_index]
        except IndexError:
            console.print(
                f'Invalid solve #{ self.solve_id }',
                style='warning',
            )
            return None

        return solve

    def confirm(self, text: str, solve: Solve) -> bool:
        """
        Display solve details and prompt user for confirmation.

        Args:
            text: The confirmation question to display.
            solve: The solve object to display details for.

        Returns:
            True if user confirms with 'y', False otherwise.

        """
        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        flag_class = 'result'
        if solve.flag == DNF:
            flag_class = 'dnf'
        if solve.flag == PLUS_TWO:
            flag_class = 'plus-two'

        header = (
            f'[localhost][link={ solve.link_term_timer }]'
            f'Solve #{ self.solve_id}'
            '[/link][/localhost]'
        )

        console.print(
            header,
            f'[time]{ format_time(solve.time) }[/time]',
            f'[date]{ date }[/date]',
            f'[{ flag_class }]{ solve.flag }[/{ flag_class }]',
        )
        if solve.advanced:
            console.print(solve.report_line)

        text += ' (y/N)'
        console.print(text, style='confirm')
        confirm = input('')

        return confirm == 'y'

    def save(self) -> None:
        """Persist the current solve stack to disk."""
        save_solves(self.cube, self.session, self.stack)

    def update(self, flag: SolveFlagInput) -> None:
        """
        Update the flag status of the solve with user confirmation.

        Args:
            flag: The new flag value to apply (OK, DNF, or +2).

        """
        if self.solve is None:
            return

        if self.confirm(
                f'Are you sure to mark this solve as "{ flag }" ?',
                self.solve,
        ):
            normalized_flag: SolveFlag = '' if flag == 'OK' else flag

            self.stack[self.solve_index].flag = normalized_flag
            self.save()

            console.print(
                f'Solve #{ self.solve_id } updated',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } untouched',
                style='caution',
            )

    def delete(self) -> None:
        """Permanently delete the solve after user confirmation."""
        if self.solve is None:
            return

        if self.confirm(
                'Are you sure you want to permanently delete this solve ?',
                self.solve,
        ):
            self.stack.pop(self.solve_index)
            self.save()

            console.print(
                f'Solve #{ self.solve_id } deleted',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } untouched',
                style='caution',
            )


class SessionManager:
    """
    Manages session-level operations and displays session summaries.

    This class provides utilities for viewing and organizing sessions across
    all cube sizes, displaying aggregated statistics and metadata for each
    session.
    """

    @staticmethod
    def index() -> None:
        """
        Display a summary table of all sessions across all cube sizes.

        For each cube size with recorded solves, display a table showing
        session names, total solve counts, last solve timestamps, and best
        times.
        """
        sessions: dict[int, dict[str, list[Solve]]] = {}

        for cube in CUBE_SIZES:
            solves = load_all_solves(cube, [], [], [])
            sessions[cube] = {}
            for solve in solves:
                sessions[cube].setdefault(
                    solve.session, [],
                ).append(
                    solve,
                )

        for cube, session_solves in sessions.items():
            if not session_solves:
                continue

            table = Table(
                title=f'Cube { cube }x{ cube }x{ cube }',
                box=box.SIMPLE,
            )
            table.add_column('Name', width=30)
            table.add_column('Total', width=5, justify='right')
            table.add_column('Last solve', width=16)
            table.add_column('Best', width=10)

            names = sorted(session_solves.keys())

            for name in names:
                session = session_solves[name]
                stats = Statistics(session)
                last_solve_date = (
                    session[-1].datetime.astimezone().strftime(
                        '%Y-%m-%d %H:%M',
                    )
                )

                table.add_row(
                    f'[stats]{ name }[/stats] ',
                    f'[result]{ len(session_solves[name]) }[/result]',
                    f'[date]{ last_solve_date }[/date]',
                    f'[time]{ format_time(stats.best) }[/time]',
                )
            console.print(table)
