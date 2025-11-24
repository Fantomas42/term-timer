"""Detail panel for displaying solve information."""

from typing import cast

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import RichLog
from textual.widgets import Static

from term_timer.formatter import format_grade
from term_timer.formatter import format_score
from term_timer.formatter import format_time
from term_timer.solve import Solve


class DetailPanel(VerticalScroll):
    """Panel displaying detailed solve information."""

    DEFAULT_CSS = """
    DetailPanel {
        width: 1fr;
        border-top: solid $primary;
    }

    DetailPanel > Static {
        background: $boost;
        padding: 1;
        text-style: bold;
    }

    DetailPanel RichLog {
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        """Initialize the detail panel."""
        super().__init__()
        self.current_solve: Solve | None = None

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the detail panel.

        Yields:
            Widget components for the detail panel layout.

        """
        yield Static('Solve Detail')
        yield RichLog(highlight=True, markup=True, wrap=True)

    def display_solve(  # noqa: C901, PLR0912, PLR0914, PLR0915
        self,
        solve: Solve,
        solve_index: int,
        cube_size: int,
    ) -> None:
        """
        Display detailed information for a solve.

        Args:
            solve: Solve object to display.
            solve_index: 1-based index of the solve.
            cube_size: Cube dimension (e.g., 3 for 3x3x3).

        """
        self.current_solve = solve
        self.current_solve.orientation = 'auto'

        # Update header
        header = self.query_one(Static)
        header.update(
            f'Solve Detail: {cube_size}x{cube_size}x{cube_size} #{solve_index}',
        )

        # Get log widget
        log = self.query_one(RichLog)
        log.clear()

        # Format date
        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        # Basic information
        log.write(
            f'[bold cyan]Time:[/bold cyan]       '
            f'[green]{format_time(solve.time)}[/green] {solve.flag}',
        )
        log.write(f'[bold cyan]Date:[/bold cyan]       [dim]{date}[/dim]')
        log.write(
            f'[bold cyan]Session:[/bold cyan]    '
            f'[yellow]{solve.session.title()}[/yellow]',
        )

        if solve.device:
            log.write(
                f'[bold cyan]Cube:[/bold cyan]       '
                f'[magenta]{solve.device}[/magenta]',
            )

        if solve.timer:
            log.write(
                f'[bold cyan]Timer:[/bold cyan]      '
                f'[magenta]{solve.timer}[/magenta]',
            )

        # Advanced metrics (if available)
        if solve.advanced:
            log.write('')
            log.write('[bold yellow]═══ Metrics ═══[/bold yellow]')

            solve_score = cast('float', solve.score)
            grade = format_grade(solve_score)
            grade_text = f'{grade:<2} {format_score(solve_score)}'
            log.write(
                f'[bold cyan]Grade:[/bold cyan]      '
                f'[bold green]{grade_text}[/bold green]',
            )

            method_applied = cast('object', solve.method_applied)
            if hasattr(method_applied, 'score'):
                method_score = method_applied.score
                method_grade = format_grade(method_score)
                method_grade_text = (
                    f'{method_grade:<2} {format_score(method_score)}'
                )
                log.write(
                    f'[bold cyan]Method:[/bold cyan]     '
                    f'[bold green]{method_grade_text}[/bold green]',
                )

            recognition_time = format_time(
                solve.recognition_time,
                allow_dnf=False,
            )
            recog_percent = solve.recognition_time / solve.time * 100.0
            log.write(
                f'[bold cyan]Recognition:[/bold cyan] '
                f'{recognition_time} ({recog_percent:.2f}%)',
            )

            execution_time = format_time(
                solve.execution_time,
                allow_dnf=False,
            )
            exec_percent = solve.execution_time / solve.time * 100.0
            log.write(
                f'[bold cyan]Execution:[/bold cyan]   '
                f'{execution_time} ({exec_percent:.2f}%)',
            )

            # Metrics
            if hasattr(solve, 'reconstruction'):
                metrics = solve.reconstruction.metrics
                log.write(
                    f'[bold cyan]Metrics:[/bold cyan]    '
                    f'{metrics.htm} HTM, {metrics.qtm} QTM, '
                    f'{solve.tps:.2f} TPS',
                )

            # Overhead
            all_missed = solve.all_missed_moves
            if all_missed:
                overhead_text = f'{all_missed} QTM overhead'
                if solve.execution_missed_moves:
                    overhead_text += (
                        f' (+{solve.execution_missed_moves} execution)'
                    )
                if solve.transition_missed_moves:
                    overhead_text += (
                        f' (+{solve.transition_missed_moves} transition)'
                    )
                log.write(
                    f'[bold cyan]Overhead:[/bold cyan]   '
                    f'[red]{overhead_text}[/red]',
                )
            else:
                log.write(
                    '[bold cyan]Overhead:[/bold cyan]   '
                    '[green]Optimal execution[/green]',
                )

            # Pauses
            if solve.execution_pauses:
                log.write(
                    f'[bold cyan]Pauses:[/bold cyan]     '
                    f'[yellow]{solve.execution_pauses}[/yellow]',
                )
            else:
                log.write(
                    '[bold cyan]Pauses:[/bold cyan]     [green]None[/green]',
                )

            # Rotations and AUFs
            if solve.rotations:
                log.write(
                    f'[bold cyan]Rotations:[/bold cyan]  '
                    f'[yellow]{solve.rotations}[/yellow]',
                )

            if solve.aufs:
                log.write(
                    f'[bold cyan]AUFs:[/bold cyan]       '
                    f'[dim]{solve.aufs}[/dim]',
                )

        # Scramble
        log.write('')
        log.write('[bold yellow]═══ Scramble ═══[/bold yellow]')
        log.write(f'[dim]{solve.scramble}[/dim]')

        # Reconstruction
        if solve.advanced and hasattr(solve, 'method_line'):
            log.write('')
            log.write(
                f'[bold yellow]═══ Reconstruction '
                f'({solve.method_analyser.name}) ═══[/bold yellow]',
            )

            # Display method line (with Rich markup)
            method_line = solve.method_line
            if method_line:
                # Split into lines and write each
                for line in method_line.split('\n'):
                    if line.strip():
                        log.write(line)

            # Links
            log.write('')
            log.write(
                f'[link={solve.link_term_timer}]View in Term-Timer[/link]',
            )
            log.write(
                f'[link={solve.link_alg_cubing}]View on alg.cubing.net[/link]',
            )
            log.write(
                f'[link={solve.link_cube_db}]View on cubedb.net[/link]',
            )
