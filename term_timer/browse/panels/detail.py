"""Detail panel for displaying solve information."""
from rich.color import ColorSystem
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import RichLog
from textual.widgets import Static

from term_timer.config import CUBE_METHOD
from term_timer.config import DISPLAY_CONFIG
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter


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
        yield RichLog(
            highlight=True, markup=True, wrap=True, auto_scroll=False,
        )

    def display_solve(
        self,
        solve: Solve,
        solve_index: int,
        cube_size: int,
        stack: list[Solve],
    ) -> None:
        """
        Display detailed information for a solve.

        Reuses the rendering of the ``detail`` command
        (SolveStatisticsReporter.detail) by capturing its Rich console
        output and replaying it in the panel, keeping the browser and the
        CLI strictly consistent.

        Args:
            solve: Solve object to display.
            solve_index: 1-based index of the solve within the stack.
            cube_size: Cube dimension (e.g., 3 for 3x3x3).
            stack: Full list of solves for the session, used as the
                reporter stack so the solve can be analysed in context.

        """
        self.current_solve = solve

        header = self.query_one(Static)
        header.update(
            f'Solve Detail: { cube_size }x{ cube_size }x{ cube_size } '
            f'#{ solve_index }',
        )

        log = self.query_one(RichLog)
        log.clear()

        reporter = SolveStatisticsReporter(cube_size, stack)

        rendered = self.render_detail(reporter, solve_index, log)
        log.write(rendered)

        # Keep the panel pinned to the top when switching solves rather
        # than following the freshly written content to the bottom.
        log.scroll_home(animate=False)
        self.scroll_home(animate=False)

    @staticmethod
    def render_detail(
        reporter: SolveStatisticsReporter,
        solve_index: int,
        log: RichLog,
    ) -> Text:
        """
        Render the detail command output to a Rich Text object.

        Forces a truecolor system and a fixed width on the shared console,
        captures everything the detail command prints (metrics, scramble,
        reconstruction, graphs, highlights and doctor diagnostics), then
        converts the captured ANSI back to a styled Text.

        Args:
            reporter: Reporter holding the session stack.
            solve_index: 1-based index of the solve to detail.
            log: Target log widget, used to match the capture width.

        Returns:
            Styled Text reproducing the detail command output.

        """
        width = log.content_size.width or 80

        original_width = console.width
        # Rich exposes no public setter for the color system, but it must
        # be forced so the capture keeps ANSI styling even when the console
        # is not attached to a color-capable terminal.
        original_color_system = console._color_system  # noqa: SLF001
        console.width = width
        console._color_system = ColorSystem.TRUECOLOR  # noqa: SLF001
        try:
            with console.capture() as capture:
                reporter.detail(
                    solve_index,
                    CUBE_METHOD,
                    'auto',
                    disable_rotations=False,
                    show_highlights=DISPLAY_CONFIG.get('highlights', True),
                    show_doctor=DISPLAY_CONFIG.get('doctor', True),
                    show_cube=DISPLAY_CONFIG.get('scramble', True),
                    show_reconstruction=DISPLAY_CONFIG.get(
                        'reconstruction', True,
                    ),
                    show_tps_graph=DISPLAY_CONFIG.get('tps_graph', True),
                    show_time_graph=DISPLAY_CONFIG.get('time_graph', True),
                    show_fluency_graph=DISPLAY_CONFIG.get(
                        'fluency_graph', True,
                    ),
                    show_recognition_graph=DISPLAY_CONFIG.get(
                        'recognition_graph', True,
                    ),
                )
        finally:
            console.width = original_width
            console._color_system = original_color_system  # noqa: SLF001

        return Text.from_ansi(capture.get())
