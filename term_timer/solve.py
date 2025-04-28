import difflib
from datetime import datetime
from datetime import timezone
from functools import cached_property

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.size import compress_moves

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
from term_timer.methods.lbl import LBLAnalyser

METHODS = {
    'cfop': CFOPAnalyser,
    'cf4op': CF4OPAnalyser,
    'lbl': LBLAnalyser,
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
            [
                x if not x.isdigit() else int(x)
                for x in move_time.split('@')
            ]
            for move_time in self.raw_moves.split(' ')
            if move_time
        ]

    @staticmethod
    def tps(moves, time):
        if time:
            return len(moves) / (time / SECOND)
        return 0

    @cached_property
    def solution(self) -> Algorithm:
        return parse_moves([m[0] for m in self.move_times])

    @cached_property
    def solution_tps(self) -> float:
        return self.tps(self.solution, self.time)

    @cached_property
    def reconstructed(self) -> list[str, int]:
        applied = self.method_applied

        if applied:
            return self.method_applied.reconstruction.copy()

        reconstruction = CUBE_ORIENTATION + self.solution

        return reconstruction.transform(
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
            to_fixpoint=True,
        )

    @cached_property
    def reconstructed_tps(self) -> float:
        return self.tps(self.reconstructed, self.time)

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

        missed_moves = self.missed_moves(self.solution)
        missed_line = f'[missed]{ missed_moves } missed moves[/missed]'
        if not missed_moves:
            missed_line = '[green]No missed move[/green]'

        return (
            f'[extlink][link={ self.link }]alg.cubing.net[/link][/extlink] '
            f'{ metric_string }'
            f'[tps]{ self.reconstructed_tps:.2f} TPS[/tps] '
            f'{ missed_line }'
        )

    @cached_property
    def method_line(self) -> str:
        if not self.method_applied:
            return ''

        line = (
            '[step]Orientation:[/step] '
            f'[consign]{ CUBE_ORIENTATION!s }[/consign]\n'
        )

        for info in self.method_applied.summary:

            header = ''
            if info['type'] == 'substep':
                header += f'[substep]- { info["name"]:<9}:[/substep] '
            else:
                header += f'[step]{ info["name"]:<11}:[/step] '

            if info['type'] == 'skipped':
                line += (
                    f'{ header }[skipped]SKIP[/skipped]\n'
                )
                continue

            footer = ''
            if info['type'] != 'virtual':
                if info['total']:
                    ratio_execution = info['execution'] / info['total'] * 12
                    ratio_inspection = info['inspection'] / info['total'] * 12
                else:
                    ratio_execution = 0
                    ratio_inspection = 0

                footer += (
                    '\n'
                    '[inspection]' +
                    (round(ratio_inspection) * ' ') +
                    '[/inspection]' +
                    (round(ratio_execution) * ' ') +
                    ' [consign]' +
                    self.missed_moves_line(info['reconstruction']) +
                    '[/consign]'
                )
                if info['cases'] and info['cases'][0]:
                    if info['name'] in {'OLL', 'PLL'}:
                        link = (
                            'https://cubing.fache.fr/'
                            f'{ info["name"] }/'
                            f'{ info["cases"][0].split(" ")[0] }.html'
                        )
                        footer += (
                            ' [comment]// '
                            f'[link={ link }]{ info["cases"][0] }[/link] ' +
                            ' '.join(info['cases'][1:]) +
                            '[/comment]'
                        )
                    else:
                        footer += (
                            ' [comment]// ' +
                            ' '.join(info['cases']) +
                            '[/comment]'
                        )

            move_klass = self.method_applied.normalize_value(
                'moves', info['name'],
                len(info['reconstruction']),
                'result',
            )
            percent_klass = self.method_applied.normalize_value(
                'percent', info['name'],
                info['total_percent'],
                'duration_p',
            )

            tps = self.tps(info['reconstruction'], info['total'])
            if not info['execution']:
                tps_exec = tps
            else:
                tps_exec = self.tps(info['reconstruction'], info['execution'])

            line += (
                f'{ header }'
                f'[{ move_klass }]'
                f'{ len(info["reconstruction"]):>2} moves[/{ move_klass }] '
                f'[inspection]'
                f'{ format_duration(info["inspection"]):>5}s[/inspection] '
                f'[inspection_p]'
                f'{ info["inspection_percent"]:5.2f}%[/inspection_p] '
                f'[execution]'
                f'{ format_duration(info["execution"]):>5}s[/execution] '
                f'[execution_p]'
                f'{ info["execution_percent"]:5.2f}%[/execution_p] '
                f'[duration]'
                f'{ format_duration(info["total"]):>5}s[/duration] '
                f'[{ percent_klass }]'
                f'{ info["total_percent"]:5.2f}%[/{ percent_klass }] '
                f'[tps]{ tps:.2f} TPS[/tps] '
                f'[tps_e]{ tps_exec:.2f} eTPS[/tps_e]'
                f'{ footer }\n'
            )

        return line

    @staticmethod
    def missed_moves_pair(algorithm) -> list[Algorithm, Algorithm]:
        source = algorithm.transform(
            optimize_double_moves,
        )
        compressed = source.transform(
            compress_moves,
        )
        return source, compressed

    def missed_moves(self, algorithm) -> int:
        source, compressed = self.missed_moves_pair(algorithm)

        return len(source) - len(compressed)

    def missed_moves_line(self, algorithm) -> str:
        source, compressed = self.missed_moves_pair(algorithm)
        if source == compressed:
            return str(source)

        moves = []
        matcher = difflib.SequenceMatcher(None, source, compressed)
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'equal':
                moves.extend(source[i1:i2])
            elif opcode == 'delete':
                moves.extend(
                    [
                        f'[red]{ item }[/red]'
                        for item in source[i1:i2]
                    ],
                )
            elif opcode == 'insert':
                moves.extend(
                    [
                        f'[green]{ item }[/green]'
                        for item in compressed[j1:j2]
                    ],
                )

            elif opcode == 'replace':
                moves.extend(
                    [
                        f'[red]{ item }[/red]'
                        for item in source[i1:i2]
                    ],
                )
                moves.extend(
                    [
                        f'[green]{ item }[/green]'
                        for item in compressed[j1:j2]
                    ],
                )

        return ' '.join([str(m) for m in moves])

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
            ).replace(
                '+', '%26%232b%3B',
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
