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

from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_duration
from term_timer.formatter import format_time
from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.methods.cfop import CFOPAnalyser

METHODS = {
    'cfop': CFOPAnalyser,
    'cf4op': CF4OPAnalyser,
}


class Solve:
    def __init__(self,
                 date: int, time: int,
                 scramble: str, flag: str = '',
                 timer: str = '',
                 device: str = '',
                 moves: list[str] | None = None):
        self.date = int(date)
        self.time = int(time)
        self.scramble = scramble
        self.flag = flag
        self.timer = timer
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
            list(
                map(
                    lambda x: x if not x.isdigit() else int(x),
                    move_time.split('@'),
                ),
            )
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
        applied = self.method_applied

        if applied:
            return self.method_applied.reconstruction.copy()

        reconstruction = self.solution.copy()
        reconstruction.insert(0, Move(CUBE_ORIENTATION))

        return reconstruction.transform(
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
    def method(self):
        return METHODS.get(CUBE_METHOD)

    @cached_property
    def method_applied(self) -> dict[str, dict]:
        if not self.raw_moves:
            return {}

        if self.method:
            return self.method(self.scramble, self.move_times)

        return {}

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

        missed_moves = f'[missed]{ self.missed_moves } missed moves[/missed]'
        if not self.missed_moves:
            missed_moves = '[green]No missed move[/green]'

        return (
            f'[extlink][link={ self.link }]alg.cubing.net[/link][/extlink] '
            f'{ metric_string }'
            f'[tps]{ self.reconstructed_tps:.2f} TPS[/tps] '
            f'{ missed_moves }'
        )

    @cached_property
    def method_line(self) -> str:
        if not self.method_applied:
            return ''

        line = (
            '[stats]Orientation  :[/stats] '
            f'[consign]{ CUBE_ORIENTATION }[/consign]\n'
        )

        for info in self.method_applied.summary:
            if info:
                line += (
                    f'[stats]{ info["name"]:<13}:[/stats] '
                    f'[consign]{ info["reconstruction"]!s }[/consign]'
                    '\n               '
                    f'[result]{ len(info["reconstruction"]):>2} moves[/result] '
                    f'[inspection]{ format_duration(info["inspection"]):>5}s[/inspection] '
                    f'[duration]{ format_duration(info["execution"]):>5}s[/duration] '
                    f'[analysis]{ format_duration(info["total"]):>5}s[/analysis]\n'
                )
            else:  # TODO fix case
                line += (
                    f'[stats]{ step }        :[/stats] [record]SKIPPED[/record]\n'
                )

        return line

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

    @cached_property
    def link(self):
        date = self.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        return self.alg_cubing_url(
            f'Solve { date }: { format_time(self.time) }'.replace(' ', '%20'),
            self.scramble,
            self.method_applied.reconstruction_detailed,
        )

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
            'timer': self.timer,
            'device': self.device,
            'moves': self.raw_moves or [],
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
