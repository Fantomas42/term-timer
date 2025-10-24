import asyncio
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube
from rich.console import Console as RichConsole

from term_timer.formatter import format_alg_moves
from term_timer.transform import humanize_moves


class Scrambler:
    """
    Mixin providing scramble tracking and display functionality.
    """

    if TYPE_CHECKING:
        # Attributes from Bluetooth mixin
        bluetooth_cube: VCube | None
        # Attributes from Console mixin
        console: RichConsole

        # Properties from Orienter mixin
        @property
        def cube_orientation_moves(self) -> Algorithm: ...

        # Methods from Orienter mixin
        def reorient(self, algorithm: Algorithm) -> Algorithm: ...
        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None: ...
        def beep(self) -> None: ...

    def __init__(self) -> None:
        super().__init__()

        self.scramble = Algorithm()
        self.scrambled = Algorithm()
        self.scramble_oriented = Algorithm()

        self.counter: int = 0

        self.facelets_scrambled = ''

        self.scramble_completed_event = asyncio.Event()

    def handle_scrambled(self, timed_move: Move) -> None:
        """
        Handle a scramble move from the bluetooth cube.
        """
        if not self.scrambled and timed_move.is_rotation_move:
            return

        self.scrambled.append(timed_move)

        is_complete = (
            self.bluetooth_cube is not None
            and self.bluetooth_cube.state == self.facelets_scrambled
        )

        if is_complete:
            self.scramble_completed_event.set()
            self.beep()

        out, full_clear = self.compute_scramble_display(
            scrambled=self.scrambled,
            scramble_oriented=self.scramble_oriented,
            cube_orientation_moves=self.cube_orientation_moves,
            is_complete=is_complete,
        )

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
            *, is_complete: bool,
    ) -> tuple[str, bool]:
        """
        Compute the display output and clear behavior for scramble progress.
        """
        if is_complete:
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
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
            for i, move in enumerate(algo):
                expected = scramble_oriented[i]
                style = 'move'
                if not on_good_way:
                    style = 'warning'
                elif expected != move:
                    on_good_way = False
                    style = 'caution' if expected[0] == move[0] else 'warning'

                out += f'[{ style }]{ move }[/{ style }] '
            full_clear = len(algo) < len(p_algo) or len(algo) <= 1

        return out, full_clear
