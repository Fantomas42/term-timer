"""Scramble tracking and display functionality."""
import asyncio
import re
import sys
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

MARKUP_TAG_RE = re.compile(r'\[/?[^\]]*\]')


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

        def back(self, size: int) -> None:
            """Move cursor back by specified number of characters."""
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

        self.misoriented_signaled = False

        self.printed_tokens: list[str] = []
        self.printed_width = 0

        self.scramble_completed_event = asyncio.Event()

    def reset_scramble_frame(self) -> None:
        """
        Forget the scramble line currently on screen.

        The incremental redraw assumes the cursor sits where the previous
        frame left it. Anything else printing in between invalidates that
        assumption, and so does starting a new attempt.
        """
        self.printed_tokens = []
        self.printed_width = 0

    def handle_scrambled(self, timed_move: Move) -> None:
        """
        Process a scramble move from the Bluetooth cube and update display.

        Tracks scramble progress by appending moves to the scrambled algorithm,
        checking for completion against the target cube state, and updating the
        terminal display with color-coded progress feedback. Emits a beep when
        the scramble is completed, a klaxon when a wrong face is turned, and a
        softer cue (only once per mistake) when the right face is turned in
        the wrong direction.

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
            SOUND_PLAYER.solve_scrambled()

        (
            out, _full_clear,
            wrong_move_added, misoriented_move, has_mismatch,
        ) = self.compute_scramble_display(
            scrambled=self.scrambled,
            scramble_oriented=self.scramble_oriented,
            cube_orientation_moves=self.cube_orientation_moves,
            is_complete=is_complete,
        )

        if wrong_move_added:
            SOUND_PLAYER.cube_move_missed()
        elif misoriented_move:
            if not self.misoriented_signaled:
                self.misoriented_signaled = True
                SOUND_PLAYER.cube_move_misoriented()
        elif not has_mismatch:
            self.misoriented_signaled = False

        self.print_scramble_frame(out, is_complete=is_complete)

    def print_scramble_frame(self, out: str, *, is_complete: bool) -> None:
        """
        Redraw the scramble line, rewriting only what changed.

        The line is prefix stable: it grows by one move most of the time, and
        only the last move changes style. Rewriting it whole makes the cursor
        sweep the entire line at every move, which reads as flickering. This
        rewinds to the first token that differs and reprints from there, the
        way `print_timer` rewinds over the time field.

        The rewind, the blanking of the stale tail and the new tail all land
        in a single write, because backspaces and spaces do not flush.

        Args:
            out: The formatted scramble progress, with Rich markup.
            is_complete: Whether the scramble has been fully completed.

        """
        prefix = f'[applied]Applying #{ self.counter }:[/applied]'

        if is_complete:
            # The completion message holds several tags separated by spaces,
            # so it cannot be split into individually balanced tokens.
            tokens = [prefix, out.strip()]
        else:
            tokens = [prefix, *out.split()]

        if tokens == self.printed_tokens:
            return

        if not self.printed_tokens:
            # First frame: the cursor sits wherever the previous display
            # left it, at the end of the prompt line, which has to go.
            self.clear_line(full=True)

        widths = [
            len(MARKUP_TAG_RE.sub('', token))
            for token in tokens
        ]

        common = 0
        for printed, token in zip(self.printed_tokens, tokens, strict=False):
            if printed != token:
                break
            common += 1

        width = sum(widths) + len(tokens) - 1

        # Column where the first differing token starts, just past the
        # separator preceding it, capped at the end of the line for a new
        # frame that is a strict prefix of the printed one.
        head_width = min(sum(widths[:common]) + common, width)
        stale = self.printed_width - head_width

        if stale > 0:
            self.back(stale)
            print(' ' * stale, end='')  # noqa: T201
            self.back(stale)

        tail = ' '.join(tokens[common:])
        if tail:
            if stale < 0:
                print(' ' * -stale, end='')  # noqa: T201
            self.console.print(tail, end='')
        else:
            # The blanking above is the whole frame, nothing flushes it.
            sys.stdout.flush()

        self.printed_tokens = tokens
        self.printed_width = width

    def compute_scramble_display(
            self,
            scrambled: Algorithm,
            scramble_oriented: Algorithm,
            cube_orientation_moves: Algorithm,
            *,
            is_complete: bool,
    ) -> tuple[str, bool, bool, bool, bool]:
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
            a boolean indicating whether to perform a full line clear,
            a boolean indicating whether the last move was a wrong move,
            a boolean indicating whether the last move turned the right face
            in the wrong direction while a non-double move was expected, and
            a boolean indicating whether any move in the sequence still
            diverges from the expected scramble.

        """
        if is_complete:
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
            wrong_move_added = False
            misoriented_move = False
            has_mismatch = False
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
                untime_moves,
            )

            is_correcting = len(str(algo)) < len(str(p_algo))

            on_good_way = True
            wrong_move_added = False
            misoriented_move = False
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

                if is_last and style == 'warning' and not is_correcting:
                    wrong_move_added = True

                if is_last and style == 'caution' and not expected.is_double:
                    misoriented_move = True

                out += f'[{ style }]{ move }[/{ style }] '
            full_clear = len(algo) < len(p_algo) or len(algo) <= 1
            has_mismatch = not on_good_way

        return (
            out, full_clear,
            wrong_move_added, misoriented_move, has_mismatch,
        )
