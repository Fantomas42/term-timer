"""Scramble tracking and display functionality."""
import asyncio
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move
from cubing_algs.transform.rotation import remove_rotations
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube

from term_timer.formatter import format_alg_moves
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.transform import humanize_moves

if TYPE_CHECKING:
    from rich.console import Console as RichConsole


class Scrambler:
    """Mixin providing scramble tracking and display functionality."""

    if TYPE_CHECKING:
        # Attributes from Bluetooth mixin
        bluetooth_cube: VCube | None
        # Attributes from Console mixin
        console: RichConsole

        # Properties from Orienter mixin
        @property
        def cube_orientation_moves(self) -> Algorithm:
            """Gets the cube orientation moves from the Orienter mixin."""
            ...

        # Methods from Orienter mixin
        def reorient(self, algorithm: Algorithm) -> Algorithm:
            """Reorient an algorithm based on cube orientation."""
            ...

        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None:
            """Clear the current terminal line."""
            ...

    def __init__(self) -> None:
        """
        Initialize scramble tracking state and event handling.

        Sets up empty algorithm containers for scramble tracking, initializes
        the scramble counter, and creates an event for scramble completion
        detection.
        """
        super().__init__()

        self.scramble = Algorithm()
        self.scrambled = Algorithm()
        self.scramble_oriented = Algorithm()

        self.counter: int = 0

        self.facelets_scrambled = ''

        self.scramble_completed_event = asyncio.Event()

    def handle_scrambled(self, timed_move: Move) -> None:
        """
        Process a scramble move from the Bluetooth cube and update display.

        Tracks scramble progress by appending moves to the scrambled algorithm,
        checking for completion against the target cube state, and updating the
        terminal display with color-coded progress feedback. Emits a beep when
        the scramble is completed.

        Args:
            timed_move: The move received from the Bluetooth cube, including
                timing information.

        """
        if self.bluetooth_cube is None:
            return

        if not self.scrambled and timed_move.is_rotation_move:
            return

        self.scrambled.append(timed_move)

        reduced_scrambled = self.scrambled.transform(
            compress_moves,
            remove_rotations,
        )
        if not reduced_scrambled:
            self.scrambled = Algorithm()

        cube_scrambled = VCube(
            self.facelets_scrambled,
            size=self.bluetooth_cube.size,
            check=False,
        )

        is_complete = self.bluetooth_cube.is_equal(cube_scrambled, strict=False)

        if is_complete:
            self.scramble_completed_event.set()
            SOUND_PLAYER.scrambled()

        out, full_clear, wrong_move_added = self.compute_scramble_display(
            scrambled=self.scrambled,
            scramble_oriented=self.scramble_oriented,
            cube_orientation_moves=self.cube_orientation_moves,
            is_complete=is_complete,
        )

        if wrong_move_added:
            SOUND_PLAYER.missed()

        self.clear_line(full=full_clear)

        self.console.print(
            f'[scramble]Scramble #{ self.counter }:[/scramble]',
            out,
            end='',
        )

    def compute_scramble_display(
            self,
            scrambled: Algorithm,
            scramble_oriented: Algorithm,
            cube_orientation_moves: Algorithm,
            *,
            is_complete: bool,
    ) -> tuple[str, bool, bool]:
        """
        Compute the formatted display output for scramble progress.

        Generates a Rich-formatted string showing the current scramble progress
        with color-coded moves indicating correctness. When incomplete, displays
        orientation moves and color-codes each scramble move based on whether it
        matches the expected sequence (green for correct, yellow for caution,
        red for warning). When complete, displays a success message.

        Args:
            scrambled: The algorithm representing moves performed so far.
            scramble_oriented: The target scramble algorithm in oriented form.
            cube_orientation_moves: Moves needed to reorient the cube.
            is_complete: Whether the scramble has been fully completed.

        Returns:
            A tuple containing the formatted output string with Rich markup,
            a boolean indicating whether to perform a full line clear, and
            a boolean indicating whether the last move was a wrong move.

        """
        if is_complete:
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
            wrong_move_added = False
        else:
            out = ''
            if cube_orientation_moves:
                out += f'{ format_alg_moves(str(cube_orientation_moves)) } '

            algo = self.reorient(
                scrambled.transform(
                    humanize_moves,
                    compress_moves,
                    untime_moves,
                ),
            )

            p_algo = scrambled[:-1].transform(
                humanize_moves,
                compress_moves,
            )

            on_good_way = True
            wrong_move_added = False
            algo_size = len(algo)
            for i, move in enumerate(algo):
                try:
                    expected = scramble_oriented[i]
                except IndexError:
                    expected = Move('.')

                is_last = i + 1 == algo_size
                style = 'move' if not is_last else 'moves'
                if not on_good_way:
                    style = 'warning'
                elif expected != move:
                    on_good_way = False
                    style = 'caution' if expected[0] == move[0] else 'warning'

                if is_last and style == 'warning' and len(algo) >= len(p_algo):
                    wrong_move_added = True

                out += f'[{ style }]{ move }[/{ style }] '
            full_clear = len(algo) < len(p_algo) or len(algo) <= 1

        return out, full_clear, wrong_move_added
