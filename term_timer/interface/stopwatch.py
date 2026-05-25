"""Stopwatch and timer functionality for solve timing."""
import asyncio
import time
from typing import TYPE_CHECKING

from cubing_algs.constants import DEFAULT_CUBE_SIZE
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.constants import REFRESH
from term_timer.constants import SECOND
from term_timer.formatter import format_time
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.methods import get_method_analyser
from term_timer.methods.base import FaceletAnalyser

if TYPE_CHECKING:
    from cubing_algs.annotations import CubeOrientation
    from rich.console import Console as RichConsole

    from term_timer.bluetooth.annotations import MoveInfo


class StopWatch:
    """
    Mixin providing stopwatch and timer functionality for solve timing.

    This mixin provides timing functionality for speedcubing solves, including
    a visual stopwatch display that updates in real-time with color-coded time
    thresholds and optional metronome functionality.

    Attributes:
        start_time: Nanosecond timestamp when the solve started.
        end_time: Nanosecond timestamp when the solve ended.
        elapsed_time: Total elapsed time in nanoseconds.
        metronome: Interval in seconds for metronome beeps (0.0 disables).
        solve_started_event: Asyncio event signaling solve start.
        solve_completed_event: Asyncio event signaling solve completion.

    """

    if TYPE_CHECKING:
        # Attributes from Console mixin
        console: RichConsole

        # Attributes from Bluetooth mixin
        bluetooth_cube: VCube | None
        bluetooth_cube_state: str
        moves: list[MoveInfo]

        # Attributes from Cube mixin
        orientation_faces: CubeOrientation
        method: str

        # Methods from State mixin
        def set_state(self, state: str, timestamp: int | None = None) -> None:  # noqa: D102
            ...

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None: ...  # noqa: D102
        def back(self, size: int) -> None: ...  # noqa: D102

    def __init__(self) -> None:
        """Initialize the stopwatch with default timing values and events."""
        super().__init__()

        self.start_time: int = 0
        self.end_time: int = 0
        self.elapsed_time: int = 0

        self.metronome: float = 0.0
        self.show_steps: bool = False

        self.solve_started_event = asyncio.Event()
        self.solve_completed_event = asyncio.Event()

    def print_step(  # noqa: PLR0913
            self,
            style: str,
            elapsed_time: int,
            step_name: str,
            *,
            delta_time: int | None = None,
            htm: int = 0,
            last: bool = False,
    ) -> None:
        """Print a completed step with its time."""
        self.clear_line(full=False)
        extras = ''
        if delta_time is not None:
            extras = (
                f' [green]+{ format_time(delta_time) }[/green]'
                f' [htm]{ htm } HTM[/htm]'
            )
        self.console.print(
            f'[{ style }]Go Go Go:[/{ style }]',
            f'[result]{ format_time(elapsed_time) }[/result]',
            f'[step]{ step_name }[/step]{ extras }',
        )
        if not last:
            SOUND_PLAYER.solve_step()

    def build_oriented_facelets(self) -> tuple[str, 'CubeOrientation']:
        """
        Build oriented facelets and orientation from bluetooth state.

        Returns:
            A tuple of (facelets string, orientation).

        """
        orientation = (
            CUBE_ORIENTATION
            if self.orientation_faces == 'auto'
            else self.orientation_faces
        )
        cube = VCube(
            self.bluetooth_cube_state,
            size=DEFAULT_CUBE_SIZE,
            check=False,
        )
        orientation_moves = ORIENTATION_FACE_MOVES[orientation]

        if orientation_moves:
            cube.rotate(orientation_moves)

        return cube.state, orientation

    async def stopwatch(self) -> None:  # noqa: C901, PLR0912, PLR0914, PLR0915
        """
        Display a running stopwatch timer until solve is completed.

        Updates the terminal display with the current elapsed time, applying
        color-coded styles based on time thresholds (5s, 10s, 15s, etc.).
        Optionally plays metronome beeps at configured intervals. Runs until
        the solve_completed_event is set.
        """
        self.clear_line(full=True)

        tempo_elapsed = 0
        style = 'timer_base'
        previous_style = ''

        self.set_state('solving', self.start_time)

        style_thresholds = (
            (50, 'timer_50'),
            (45, 'timer_45'), (40, 'timer_40'),
            (35, 'timer_35'), (30, 'timer_30'),
            (25, 'timer_25'), (20, 'timer_20'),
            (15, 'timer_15'), (10, 'timer_10'),
            (5, 'timer_05'),
        )

        facelet_analyser: FaceletAnalyser | None = None
        groups_to_track: tuple[tuple[tuple[str, str | None], ...], ...] = ()
        group_progress = 0
        completed_in_group: set[str] = set()
        last_facelets = ''
        previous_step_time: int = 0
        previous_move_index: int = 0

        if self.show_steps:
            analyser_class = get_method_analyser(self.method)
            facelet_analyser = FaceletAnalyser()
            groups_to_track = analyser_class.step_groups or tuple(
                ((step, None),) for step in analyser_class.step_list
            )

        while not self.solve_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            elapsed_seconds = elapsed_time / SECOND
            new_tempo = int(elapsed_time / (SECOND * self.metronome or 1))

            style = next(
                (s for t, s in style_thresholds if elapsed_seconds > t),
                'timer_base',
            )

            if tempo_elapsed != new_tempo:
                tempo_elapsed = new_tempo
                if self.metronome:
                    SOUND_PLAYER.metronome_tick()

            if (
                facelet_analyser is not None
                and group_progress < len(groups_to_track)
                and self.bluetooth_cube is not None
                and self.bluetooth_cube_state != last_facelets
            ):
                last_facelets = self.bluetooth_cube_state
                facelets, orientation = self.build_oriented_facelets()
                current_group = groups_to_track[group_progress]

                for step_name, display_name in current_group:
                    if (
                        step_name not in completed_in_group
                        and facelet_analyser.check_step(
                            step_name, facelets, orientation,
                        )
                    ):
                        delta_time = (
                            elapsed_time - previous_step_time
                            if previous_step_time
                            else None
                        )
                        step_htm = parse_moves(
                            m['move'] for m in self.moves[previous_move_index:]
                        ).transform(
                            optimize_double_moves,
                        ).metrics.htm

                        self.print_step(
                            style,
                            elapsed_time,
                            display_name or step_name,
                            delta_time=delta_time,
                            htm=step_htm,
                        )
                        previous_step_time = elapsed_time
                        previous_move_index = len(self.moves)
                        completed_in_group.add(step_name)
                        previous_style = ''

                if len(completed_in_group) == len(current_group):
                    group_progress += 1
                    completed_in_group = set()

            if style != previous_style:
                previous_style = style
                self.clear_line(full=False)
                self.console.print(
                    f'[{ style }]Go Go Go:[/{ style }]',
                    f'[result]{ format_time(elapsed_time) }[/result]',
                    end='',
                )
            else:
                self.back(9)
                self.console.print(
                    f'[result]{ format_time(elapsed_time) }[/result]',
                    end='',
                )

            await asyncio.sleep(REFRESH)

        if (
            facelet_analyser is not None
            and group_progress < len(groups_to_track)
            and self.bluetooth_cube is not None
        ):
            facelets, orientation = self.build_oriented_facelets()
            current_group = groups_to_track[group_progress]
            final_elapsed_time = self.end_time - self.start_time

            for step_name, display_name in current_group:
                if (
                    step_name not in completed_in_group
                    and facelet_analyser.check_step(
                        step_name, facelets, orientation,
                    )
                ):
                    delta_time = (
                        final_elapsed_time - previous_step_time
                        if previous_step_time
                        else None
                    )
                    step_htm = parse_moves(
                        m['move'] for m in self.moves[previous_move_index:]
                    ).transform(
                        optimize_double_moves,
                    ).metrics.htm

                    self.print_step(
                        style,
                        final_elapsed_time,
                        display_name or step_name,
                        delta_time=delta_time,
                        htm=step_htm,
                        last=True,
                    )
                    previous_step_time = final_elapsed_time
                    previous_move_index = len(self.moves)

        self.set_state('stop')
