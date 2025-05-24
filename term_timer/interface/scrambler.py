import asyncio

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.size import compress_moves


class Scrambler:
    scramble = []
    scrambled = []
    scramble_oriented = []

    facelets_scrambled = ''

    scramble_completed_event = asyncio.Event()

    def handle_scrambled(self, count):
        if self.bluetooth_cube.state == self.facelets_scrambled:
            self.scramble_completed_event.set()
            self.beep()
            out = (
                '[result]Cube scrambled and ready to be solved ![/result] '
                '[consign]Start solving to launch the timer.[/consign]'
            )
            full_clear = True
        else:
            out = ''
            algo = self.reorient(
                parse_moves(self.scrambled).transform(compress_moves),
            )
            p_algo = self.reorient(
                parse_moves(self.scrambled[:-1]).transform(compress_moves),
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
            f'[scramble]Scramble #{ count }:[/scramble]',
            out,
            end='',
        )
