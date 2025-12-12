"""Solve and session management utilities for editing and deleting solves."""
import json
import operator
from datetime import datetime
from datetime import timezone
from pathlib import Path
from random import Random

from rich import box
from rich.table import Table

from term_timer.constants import CUBE_SIZES
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.formatter import format_flag
from term_timer.formatter import format_float
from term_timer.formatter import format_session_name
from term_timer.formatter import format_term_timer_session_url
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.printer import print_cube_scrambled
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.solve import SolveData
from term_timer.stats import SolveStatisticsReporter


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

    def display_solve(self) -> None:
        """Display solve details before editing."""
        if self.solve is None:
            return

        date = self.solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        header = (
            f'[localhost][link={ self.solve.link_term_timer }]'
            f'Solve #{ self.solve_id}'
            '[/link][/localhost]'
        )

        console.print(
            header,
            f'[time]{ format_time(self.solve.time) }[/time]',
            f'[date]{ date }[/date]',
            format_flag(self.solve.flag),
        )
        if self.solve.advanced:
            console.print(self.solve.report_line)

    @staticmethod
    def confirm(text: str) -> bool:
        """
        Display solve details and prompt user for confirmation.

        Args:
            text: The confirmation question to display.

        Returns:
            True if user confirms with 'y', False otherwise.

        """
        confirm = console.input(f'[confirm]{ text } (y/N)[/confirm] ')

        return confirm == 'y'

    def save(self) -> None:
        """Persist the current solve stack to disk."""
        save_solves(self.cube, self.session, self.stack)

    def update_flag(self, flag: SolveFlagInput, *, yes: bool = False) -> None:
        """
        Update the flag status of the solve with user confirmation.

        Args:
            flag: The new flag value to apply (OK, DNF, or +2).
            yes: If True, skip confirmation prompt.

        """
        if self.solve is None:
            return

        if yes or self.confirm(
                f'Are you sure to mark this solve as "{ flag }" ?',
        ):
            normalized_flag: SolveFlag = '' if flag == 'OK' else flag

            self.stack[self.solve_index].flag = normalized_flag
            self.save()

            console.print(
                f'Solve #{ self.solve_id } flag updated',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } flag untouched',
                style='caution',
            )

    def update_comment(self, comment: str, *, yes: bool = False) -> None:
        """
        Update the comment of the solve with user confirmation.

        Args:
            comment: The new comment to apply.
            yes: If True, skip confirmation prompt.

        """
        if self.solve is None:
            return

        if yes or self.confirm(
                f'Are you sure to update the comment to "{ comment }" ?',
        ):
            self.stack[self.solve_index].comment = comment
            self.save()

            console.print(
                f'Solve #{ self.solve_id } comment updated',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } comment untouched',
                style='caution',
            )

    def delete(self) -> None:
        """Permanently delete the solve after user confirmation."""
        if self.solve is None:
            return

        if self.confirm(
                'Are you sure you want to permanently delete this solve ?',
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
            table.add_column('Bluetooth', width=7, justify='right')
            table.add_column('Last solve', width=16)
            table.add_column('Best', width=10)

            names = sorted(session_solves.keys())

            for name in names:
                session = session_solves[name]
                stats = SolveStatisticsReporter(cube, session)
                last_solve_date = (
                    session[-1].datetime.astimezone().strftime(
                        '%Y-%m-%d %H:%M',
                    )
                )

                url = format_term_timer_session_url(cube, name)
                total = len(session_solves[name])
                connected_percent = format_float(stats.advanced_solves * 100)

                table.add_row(
                    f'[localhost][link={ url }]{ format_session_name(name) }'
                    '[/link][/localhost]',
                    f'[result]{ total }[/result]',
                    f'[bluetooth]{ connected_percent }%[/bluetooth]',
                    f'[date]{ last_solve_date }[/date]',
                    f'[time]{ format_time(stats.best) }[/time]',
                )
            console.print(table)

    @staticmethod
    def merge(session_paths: list[str]) -> None:
        """
        Merge solves from multiple sessions, sorted by date.

        Deduplicates solves based on the date field. If multiple solves
        have the same date, only the last one encountered is kept.

        Args:
            session_paths: List of session path to merge.

        """
        solves_dict: dict[int, SolveData] = {}
        for session_path in session_paths:
            path = Path(session_path)
            if not path.exists():
                console.print(
                    f'Invalid solve file "{ path }"',
                    style='warning',
                )
                continue
            with path.open('r', encoding='utf-8') as fd:
                data: list[SolveData] = json.load(fd)
            for solve in data:
                solves_dict[solve['date']] = solve

        all_solves = list(solves_dict.values())
        all_solves.sort(key=operator.itemgetter('date'))

        out = json.dumps(
            all_solves,
            indent=1,
        )
        print(out)  # noqa: T201


class ScrambleManager:
    """
    Generates and displays multiple cube scrambles for practice sessions.

    This class creates random scrambles for speedcubing practice outside of
    the timer, with optional cube visualization and scramble analysis.
    """

    def __init__(  # noqa: PLR0913
            self, *,
            cube_size: int,
            scrambles: int,
            iterations: int,
            easy_cross: bool,
            show_cube: bool,
            output_format: str,
            seed: str,
            rng: Random,
    ) -> None:
        """
        Initialize the ScrambleManager with scramble generation parameters.

        Args:
            cube_size: The cube size (e.g., 3 for 3x3x3).
            scrambles: The number of scrambles to generate.
            iterations: The number of random moves per scramble (0 for auto).
            easy_cross: Whether to generate scrambles with easy crosses.
            show_cube: Whether to display visual cube representations.
            output_format: Output format ('terminal' or 'markdown').
            seed: Seed used for the RNG.
            rng: Random number generator.

        """
        self.cube_size = cube_size
        self.scrambles = scrambles
        self.iterations = iterations
        self.easy_cross = easy_cross
        self.show_cube = show_cube
        self.output_format = output_format
        self.seed = seed
        self.rng = rng

    def run(self) -> None:
        """
        Generate and display the configured number of scrambles.

        Routes to the appropriate output method based on format setting.
        """
        if self.output_format == 'markdown':
            self.run_markdown()
        else:
            self.run_terminal()

    def run_terminal(self) -> None:
        """
        Generate and display scrambles in terminal format.

        For each scramble, displays the move sequence and optionally shows
        the cube visualization with scrambled percentage (3x3x3 only).
        """
        for counter in range(self.scrambles):
            scramble, cube = scrambler(
                cube_size=self.cube_size,
                iterations=self.iterations,
                easy_cross=self.easy_cross,
                rng=self.rng,
            )
            scramble_line = (
                f'[scramble]Scramble #{ counter + 1 }:[/scramble] '
                f'[moves]{ scramble }[/moves] '
                f'[comment]// { scramble.metrics.htm } HTM[/comment]'
            )

            if self.cube_size == 3 and not self.show_cube:
                scrambled_percent = (
                    scramble.impacts.facelets_scrambled_percent * 100
                )
                scramble_line += (
                    f' [comment]{ format_float(scrambled_percent) }%[/comment]'
                )

            console.print(scramble_line)

            if self.show_cube:
                print_cube_scrambled(cube, 'UF', scramble)

    def run_markdown(self) -> None:
        """
        Generate and display scrambles in markdown format.

        Produces a formatted markdown document with metadata header,
        scramble sequences, HTM counts, and optional emoji cube visualizations.
        """
        output_lines: list[str] = []

        # Document header
        output_lines.extend(('# Scrambles', ''))

        # Metadata section
        now = datetime.now(timezone.utc).astimezone()  # noqa: UP017
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

        cube_size_str = (
            f'**Cube Size:** '
            f'{ self.cube_size }x{ self.cube_size }x{ self.cube_size }'
        )
        output_lines.extend((
            f'**Generated:** { timestamp }',
            cube_size_str,
            f'**Count:** { self.scrambles }',
            '**Parameters:**',
        ))
        params = []

        if self.seed:
            params.append(f'- Seed: { self.seed }')
        else:
            params.append('- Seed: Random')

        if self.iterations:
            params.append(f'- Iterations: { self.iterations }')
        else:
            params.append('- Iterations: Auto')

        params.append(f'- Easy Cross: { "Yes" if self.easy_cross else "No" }')

        output_lines.extend(params)
        output_lines.extend(('', '---', ''))

        # Generate scrambles
        for counter in range(self.scrambles):
            scramble, cube = scrambler(
                cube_size=self.cube_size,
                iterations=self.iterations,
                easy_cross=self.easy_cross,
                rng=self.rng,
            )

            # Scramble header and details
            output_lines.extend((
                f'## Scramble #{ counter + 1 }',
                '',
                f'**Moves:** { scramble }',
                f'**HTM:** { scramble.metrics.htm }',
            ))

            # Add scrambled percentage for 3x3x3
            if self.cube_size == 3:
                scrambled_percent = (
                    scramble.impacts.facelets_scrambled_percent * 100
                )
                scrambled_str = (
                    f'**Scrambled:** { format_float(scrambled_percent) }%'
                )
                output_lines.append(scrambled_str)

            # Cube visualization if requested
            if self.show_cube:
                output_lines.extend(('', '### Cube Visualization', ''))

                cube_emoji = cube.display(orientation='UF', facelet='emoji')
                output_lines.extend((
                    '```',
                    cube_emoji.rstrip('\n'),
                    '```',
                    '',
                ))

            output_lines.extend(('---', ''))

        # Print the complete markdown document
        print('\n'.join(output_lines))  # noqa: T201
