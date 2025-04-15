from datetime import datetime
from datetime import timezone
from functools import cached_property

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_do_undo_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.optimize import optimize_repeat_three_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_m_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_time


class Solve:
    def __init__(self,
                 date: int, time: int,
                 scramble: str, flag: str = '',
                 device: str = '',
                 moves: list[str] | None = None):
        self.date = int(date)
        self.time = int(time)
        self.scramble = scramble
        self.flag = flag
        self.device = device
        self.raw_moves = moves

    @cached_property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(
            self.date, tz=timezone.utc,  # noqa: UP017
        )

    @cached_property
    def final_time(self) -> int:
        if self.flag == PLUS_TWO:
            return self.time + (2 * SECOND)
        if self.flag == DNF:
            return 0

        return self.time

    @cached_property
    def move_times(self) -> list[str, int]:
        return [
            move_time.split('@')
            for move_time in self.raw_moves.split(' ')
            if move_time
        ]

    @cached_property
    def solution(self) -> Algorithm:
        return parse_moves([m[0] for m in self.move_times])

    @cached_property
    def solution_tps(self) -> float:
        return len(self.solution) / (self.time / SECOND)

    @cached_property
    def reconstructed(self) -> list[str, int]:
        reconstruction = self.solution.copy()
        reconstruction.insert(0, Move(CUBE_ORIENTATION))

        return reconstruction.transform(
            reslice_m_moves,
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
            to_fixpoint=True,
        )

    @cached_property
    def reconstructed_tps(self) -> float:
        return len(self.reconstructed) / (self.time / SECOND)

    @cached_property
    def missed_moves(self) -> int:
        return len(self.solution) - len(
            self.solution.transform(
                optimize_do_undo_moves,
                optimize_repeat_three_moves,
                to_fixpoint=True,
            ),
        )

    @cached_property
    def report_line(self) -> str:
        if not self.raw_moves:
            return ''

        metric_string = ''
        metrics = STATS_CONFIG.get('metrics')
        for metric in metrics:
            value = self.reconstructed.metrics[metric]
            metric_string += (
                f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
            )

        date = self.datetime.astimezone().strftime('%Y-%m-%d %H:%M')
        link = self.alg_cubing_url(
            f'Solve { date }: { format_time(self.time) }'.replace(' ', '%20'),
            self.scramble,
            'z2 // Orientation\n' + str(self.reconstructed),
        )

        missed_moves = f'[missed]{ self.missed_moves } missed moves[/missed]'
        if not self.missed_moves:
            missed_moves = '[green]No missed move[/green]'

        return (
            f'[extlink][link={ link }]alg.cubing.net[/link][/extlink] '
            f'{ metric_string }'
            f'[tps]{ self.reconstructed_tps:.2f} TPS[/tps] '
            f'{ missed_moves }'
        )

    @cached_property
    def missed_line(self) -> str:
        compressed = self.solution.transform(
            optimize_do_undo_moves,
            optimize_repeat_three_moves,
            to_fixpoint=True,
        )

        moves = []
        missed = 0
        for i, m in enumerate(self.solution):
            if i - missed < len(compressed):
                if m == compressed[i - missed]:
                    moves.append(str(m))
                else:
                    moves.append(f'[warning]{ m!s }[/warning]')
                    missed += 1
            else:
                moves.append(str(m))

        return ' '.join(moves)

    @staticmethod
    def alg_cubing_url(title: str, setup: str, alg: str) -> str:
        def clean(string: str) -> str:
            return string.replace(
                ' ', '_',
            ).replace(
                "'", '-',
            ).replace(
                '/', '%2F',
            ).replace(
                '\n', '%0A',
            )

        return (
            'https://alg.cubing.net/'
            f'?title={ title }'
            f'&alg={ clean(alg) }'
            f'&setup={ clean(setup) }'
        )

    @property
    def as_save(self):
        return {
            'date': self.date,
            'time': self.time,
            'scramble': self.scramble,
            'flag': self.flag,
            'device': self.device,
            'moves': self.raw_moves or [],
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
