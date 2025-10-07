import asyncio
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.slice import reslice_timed_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube
from rich.console import Console as RichConsole

from term_timer.constants import RESLICE_THRESHOLD


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

    def handle_scrambled(self, timed_move: str) -> None:
        """
        Handle a scramble move from the bluetooth cube.
        """
        self.scrambled += timed_move

        if (
                self.bluetooth_cube
                and self.bluetooth_cube.state == self.facelets_scrambled
        ):
            self.scramble_completed_event.set()
            self.beep()
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
        else:
            out = ''
            if self.cube_orientation_moves:
                out += f'[consign]{ self.cube_orientation_moves }[/consign] '

            algo = self.reorient(
                self.scrambled.transform(
                    reslice_timed_moves(RESLICE_THRESHOLD),
                    degrip_full_moves,
                    compress_moves,
                    untime_moves,
                ),
            )
            p_algo = self.scrambled[:-1].transform(
                reslice_timed_moves(RESLICE_THRESHOLD),
                degrip_full_moves,
                compress_moves,
            )

            on_good_way = True
            for i, move in enumerate(algo):
                expected = self.scramble_oriented[i]
                style = 'move'
                if expected != move or not on_good_way:
                    on_good_way = False
                    style = 'warning'
                    if expected[0] == move[0]:
                        style = 'caution'

                out += f'[{ style }]{ move }[/{ style }] '
            full_clear = len(algo) < len(p_algo) or len(algo) <= 1

        self.clear_line(full=full_clear)

        self.console.print(
            f'[scramble]Scramble #{ self.counter }:[/scramble]',
            out,
            end='',
        )
