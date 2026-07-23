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
from term_timer.formatter import format_duration
from term_timer.formatter import format_ghost_delta
from term_timer.formatter import format_time
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.methods import get_method_analyser
from term_timer.methods.annotations import TrackedStep
from term_timer.methods.base import FaceletAnalyser

if TYPE_CHECKING:
    from cubing_algs.annotations import CubeOrientation
    from rich.console import Console as RichConsole

    from term_timer.bluetooth.annotations import MoveInfo
    from term_timer.solve import Solve

STYLE_THRESHOLDS = (
    (50, 'timer_50'),
    (45, 'timer_45'), (40, 'timer_40'),
    (35, 'timer_35'), (30, 'timer_30'),
    (25, 'timer_25'), (20, 'timer_20'),
    (15, 'timer_15'), (10, 'timer_10'),
    (5, 'timer_05'),
)


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
        def set_state(self, state: str, timestamp: int | None = None) -> None:
            """Set the current state and log the transition."""
            ...

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None:
            """Clear the current terminal line."""
            ...

        def back(self, size: int) -> None:
            """Move cursor back by specified number of characters."""
            ...

    def __init__(self) -> None:
        """Initialize the stopwatch with default timing values and events."""
        super().__init__()

        self.start_time: int = 0
        self.end_time: int = 0
        self.elapsed_time: int = 0

        self.metronome: float = 0.0
        self.show_steps: bool = False
        self.step_width: int = 0

        self.facelet_analyser: FaceletAnalyser | None = None
        self.groups_to_track: tuple[tuple[TrackedStep, ...], ...] = ()
        self.group_progress: int = 0
        self.completed_in_group: set[str] = set()
        self.last_facelets: str = ''
        self.previous_step_time: int = 0
        self.previous_move_index: int = 0
        self.first_step: bool = True
        self.previous_style: str = ''

        self.ghost: Solve | None = None
        self.ghost_splits: dict[str, int] = {}
        self.ghost_delta: int | None = None

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
            ghost_split: int | None = None,
    ) -> None:
        """Print a completed step with its time."""
        self.clear_line(full=False)

        padded_name = (
            f'{ step_name:<{ self.step_width }}'
            if self.step_width else step_name
        )
        extras = ''
        if htm:
            extras += f' [htm]{ htm:>2} HTM[/htm]'
        if delta_time is not None:
            extras += f' [green]+{ format_duration(delta_time) }[/green]'

        if ghost_split is not None:
            ghost_delta = elapsed_time - ghost_split
            if last:
                verdict = 'WIN' if ghost_delta <= 0 else 'LOSS'
                style_v = 'record' if ghost_delta <= 0 else 'warning'
                extras += f'   👻 [{ style_v }]{ verdict }[/{ style_v }]'
            else:
                extras += (
                    f'   👻 [result]{ format_duration(ghost_split) }[/result]'
                    f' { format_ghost_delta(ghost_delta) }'
                )

        self.console.print(
            f'[{ style }]Go Go Go:[/{ style }]',
            f'[result]{ format_time(elapsed_time) }[/result]',
            f'[step]{ padded_name }[/step]{ extras }',
        )
        if not last:
            if ghost_split is None:
                SOUND_PLAYER.solve_step()
            elif elapsed_time - ghost_split <= 0:
                SOUND_PLAYER.solve_step_ahead()
            else:
                SOUND_PLAYER.solve_step_behind()

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

    def init_step_tracking(self) -> None:
        """Initialize step tracking state for a new solve."""
        self.facelet_analyser = None
        self.groups_to_track = ()
        self.group_progress = 0
        self.completed_in_group = set()
        self.last_facelets = ''
        self.previous_step_time = 0
        self.previous_move_index = 0
        self.first_step = True
        self.previous_style = ''
        self.step_width = 0
        self.ghost_splits = {}
        self.ghost_delta = None

        if not self.show_steps:
            return

        analyser_class = get_method_analyser(self.method)
        self.facelet_analyser = FaceletAnalyser()
        self.groups_to_track = analyser_class.step_groups or tuple(
            (TrackedStep(step, None),)
            for step in analyser_class.step_list
        )
        self.step_width = max(
            (
                len(display_name or step_name)
                for group in self.groups_to_track
                for step_name, display_name in group
            ),
            default=0,
        )

        if self.ghost is not None:
            self.ghost_splits = self.ghost.ghost_splits(self.groups_to_track)

    def check_and_print_steps(
            self,
            elapsed_time: int,
            style: str,
            *,
            final: bool = False,
    ) -> None:
        """Detect completed steps and print them."""
        if (
            self.facelet_analyser is None
            or self.group_progress >= len(self.groups_to_track)
            or self.bluetooth_cube is None
        ):
            return
        if not final and self.bluetooth_cube_state == self.last_facelets:
            return

        if not final:
            self.last_facelets = self.bluetooth_cube_state

        facelets, orientation = self.build_oriented_facelets()
        current_group = self.groups_to_track[self.group_progress]

        for step_name, display_name in current_group:
            if (
                step_name not in self.completed_in_group
                and self.facelet_analyser.check_step(
                    step_name, facelets, orientation,
                )
            ):
                delta_time = elapsed_time - self.previous_step_time
                step_htm = parse_moves(
                    [m['move'] for m in self.moves[self.previous_move_index:]],
                ).transform(optimize_double_moves).metrics.htm

                ghost_split = (
                    self.ghost_splits.get(step_name)
                    if self.ghost_splits else None
                )
                if ghost_split is not None:
                    self.ghost_delta = elapsed_time - ghost_split

                show_delta = final or not self.first_step
                self.print_step(
                    style,
                    elapsed_time,
                    display_name or step_name,
                    delta_time=delta_time if show_delta else None,
                    htm=step_htm,
                    last=final,
                    ghost_split=ghost_split,
                )
                self.first_step = False
                self.previous_step_time = elapsed_time
                self.previous_move_index = len(self.moves)
                self.completed_in_group.add(step_name)
                self.previous_style = ''

        if not final and len(self.completed_in_group) == len(current_group):
            self.group_progress += 1
            self.completed_in_group = set()

    def print_timer(self, elapsed_time: int, style: str) -> None:
        """Print or update the running timer display."""
        if self.ghost_splits:
            # The held ghost delta has a variable width, so the back(9)
            # fast path can't be used. The delta only changes at a
            # checkpoint (which prints its own line and starts a fresh
            # running line), so a plain redraw never leaves stale chars.
            ghost_segment = ''
            if self.ghost_delta is not None:
                delta = format_ghost_delta(self.ghost_delta)
                ghost_segment = f'   👻 { delta }'
            self.clear_line(full=False)
            self.console.print(
                f'[{ style }]Go Go Go:[/{ style }]',
                f'[result]{ format_time(elapsed_time) }[/result]'
                f'{ ghost_segment }',
                end='',
            )
            self.previous_style = style
            return

        if style != self.previous_style:
            self.previous_style = style
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

    async def stopwatch(self) -> None:
        """
        Display a running stopwatch timer until solve is completed.

        Updates the terminal display with the current elapsed time, applying
        color-coded styles based on time thresholds (5s, 10s, 15s, etc.).
        Optionally plays metronome beeps at configured intervals. Runs until
        the solve_completed_event is set.
        """
        self.clear_line(full=True)
        self.set_state('solving', self.start_time)
        self.init_step_tracking()

        tempo_elapsed = 0
        style = 'timer_base'

        while not self.solve_completed_event.is_set():
            elapsed_time = time.perf_counter_ns() - self.start_time
            elapsed_seconds = elapsed_time / SECOND
            new_tempo = int(elapsed_time / (SECOND * self.metronome or 1))

            style = next(
                (s for t, s in STYLE_THRESHOLDS if elapsed_seconds > t),
                'timer_base',
            )

            if tempo_elapsed != new_tempo:
                tempo_elapsed = new_tempo
                if self.metronome:
                    SOUND_PLAYER.metronome_tick()

            self.check_and_print_steps(elapsed_time, style)
            self.print_timer(elapsed_time, style)

            await asyncio.sleep(REFRESH)

        self.check_and_print_steps(
            self.end_time - self.start_time, style, final=True,
        )
        self.set_state('stop')
