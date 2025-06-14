import difflib
from datetime import datetime
from datetime import timezone
from functools import cached_property

import plotext as plt
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
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
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
                 session: str = '',
                 moves: list[str] | None = None):
        self.date = int(date)
        self.time = int(time)
        self.scramble = scramble
        self.flag = flag
        self.timer = timer
        self.device = device
        self.session = session or 'default'
        self.raw_moves = moves

        self.method_name = CUBE_METHOD

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
    def move_times(self) -> list[list[str | int]]:
        return [
            [
                x if not x.isdigit() else int(x)
                for x in move_time.split('@')
            ]
            for move_time in self.raw_moves.split(' ')
            if move_time
        ]

    @cached_property
    def advanced(self):
        return bool(self.raw_moves)

    @staticmethod
    def tps(moves: list[str] | int, time: int) -> float:
        if not time:
            return 0

        if not isinstance(moves, int):
            moves = len(moves)

        return moves / (time / SECOND)

    @cached_property
    def solution(self) -> Algorithm:
        return parse_moves(self.raw_moves)

    @cached_property
    def solution_tps(self) -> float:
        return self.tps(self.solution, self.time)

    @cached_property
    def reconstructed(self) -> list[str]:
        applied = self.method_applied

        if applied:
            return self.method_applied.reconstruction.copy()

        return self.reconstructed_raw

    @cached_property
    def reconstructed_raw(self) -> list[str]:
        reconstruction = CUBE_ORIENTATION + self.solution

        return reconstruction.transform(
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
            to_fixpoint=True,
        )

    @cached_property
    def reconstructed_tps(self) -> float:
        return self.tps(self.reconstructed.metrics['qtm'], self.time)

    @cached_property
    def all_missed_moves(self) -> int:
        return self.missed_moves(self.solution)

    @cached_property
    def step_missed_moves(self) -> int:
        return sum(
            self.missed_moves(parse_moves(s['moves']))
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def execution_missed_moves(self) -> int:
        return self.step_missed_moves

    @cached_property
    def transition_missed_moves(self) -> int:
        return self.all_missed_moves - self.step_missed_moves

    @cached_property
    def method(self):
        return METHODS.get(self.method_name, CF4OPAnalyser)

    @cached_property
    def method_applied(self) -> dict[str, dict]:
        if not self.advanced:
            return None

        return self.method(self.scramble, self.solution)

    @cached_property
    def recognition_time(self) -> float:
        return sum(
            s['recognition']
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def execution_time(self) -> float:
        return sum(
            s['execution']
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def move_speed(self) -> float:
        return self.execution_time / len(self.solution)

    @cached_property
    def report_line(self) -> str:
        if not self.advanced:
            return ''

        metric_string = ''
        metrics = STATS_CONFIG.get('metrics')
        for metric in metrics:
            value = self.reconstructed.metrics[metric]
            metric_string += (
                f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
            )

        missed_moves = self.all_missed_moves
        missed_line = (
            '[exec_overhead]'
            f'{ missed_moves } missed moves'
            '[/exec_overhead]'
        )
        if not missed_moves:
            missed_line = '[success]No missed move[/success]'

        grade = format_grade(self.score)
        grade_class = grade.lower()
        grade_line = (
            f' [grade_{ grade_class }]'
            f'Grade { grade }'
            f'[/grade_{ grade_class }]'
        )

        return (
            f'[extlink][link={ self.link }]alg.cubing.net[/link][/extlink] '
            f'{ metric_string }'
            f'[tps]{ self.reconstructed_tps:.2f} TPS[/tps] '
            f'{ missed_line }{ grade_line }'
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
                    ratio_recognition = info['recognition'] / info['total'] * 12
                else:
                    ratio_execution = 0
                    ratio_recognition = 0

                footer += (
                    '\n'
                    '[recognition]' +
                    (round(ratio_recognition) * ' ') +
                    '[/recognition]' +
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
                f'{ len(info["reconstruction"]):>2} HTM[/{ move_klass }] '
                f'[recognition]'
                f'{ format_duration(info["recognition"]):>5}s[/recognition] '
                f'[recognition_p]'
                f'{ info["recognition_percent"]:5.2f}%[/recognition_p] '
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

    def reconstruction_alg_cubing_pauses(self, step):
        paused = []
        threshold = self.move_speed / MS_TO_NS_FACTOR * 2
        previous_time = step['reconstruction_timed'][0].timed

        for index in range(len(step['reconstruction'])):
            time = step['reconstruction_timed'][index].timed
            if time - previous_time > threshold:
                paused.append('.' * int((time - previous_time) / threshold))

            previous_time = time
            paused.append(str(step['reconstruction'][index]))

        paused.append('.' * int((step['post_pause'] / MS_TO_NS_FACTOR) / threshold))

        return ' '.join(paused)

    @cached_property
    def reconstruction_alg_cubing(self):
        recons = ''

        if CUBE_ORIENTATION:
            recons += f'{ CUBE_ORIENTATION!s } // Orientation\n'

        for info in self.method_applied.summary:
            if info['type'] != 'virtual':

                if info['type'] == 'skipped':
                    recons += f'// { info["name"] } SKIPPED\n'
                    continue

                cases = ''
                if info['cases'] and info['cases'][0]:
                    cases = f' ({ " ".join(info["cases"]) })'

                recons += (
                    f'{ self.reconstruction_alg_cubing_pauses(info) } // '
                    f'{ info["name"] }{ cases } '
                    f'Reco: { format_duration(info["recognition"]) }s '
                    f'Exec: { format_duration(info["execution"]) }s '
                    f'Moves: { len(info["reconstruction"]) }\n'
                )

        return recons

    def time_graph(self) -> None:
        if not self.advanced:
            return

        plt.clear_figure()
        plt.scatter(
            [m[1] / 1000 for m in self.move_times],
            marker='fhd',
            label='Time',
        )

        yticks = []
        xticks = []
        xlabels = []
        for s in self.method_applied.summary:
            if s['type'] not in {'skipped', 'virtual'}:
                index = s['index'][-1] + 1
                plt.vline(index, 'red')
                xticks.append(index)
                yticks.append(self.move_times[index - 1][1] / 1000)
                xlabels.append(s['name'])

        plt.xticks(xticks, xlabels)
        plt.yticks(yticks)
        plt.plot_size(height=20)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))

        plt.show()

    def tps_graph(self) -> None:
        if not self.advanced:
            return

        plt.clear_figure()

        tpss = []
        etpss = []
        labels = []
        for s in self.method_applied.summary:
            if s['type'] not in {'skipped', 'virtual'}:
                tps = Solve.tps(s['moves'], s['total'])
                tpss.append(tps)
                etpss.append(Solve.tps(s['moves'], s['execution']) - tps)
                labels.append(s['name'])

        plt.stacked_bar(
            labels,
            [tpss, etpss],
            labels=['TPS', 'eTPS'],
            color=[119, 39],
        )
        plt.hline(self.reconstructed_tps, 'red')
        plt.plot_size(height=20)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))

        plt.show()

    def recognition_graph(self) -> None:
        if not self.advanced:
            return

        plt.clear_figure()

        labels = []
        executions = []
        recognitions = []
        for s in self.method_applied.summary:
            if s['type'] not in {'skipped', 'virtual'}:
                labels.append(s['name'])
                recognitions.append(s['recognition'] / SECOND)
                executions.append(s['execution'] / SECOND)

        plt.stacked_bar(
            labels,
            [recognitions, executions],
            labels=['Recognition', 'Execution'],
            color=[33, 202],
        )
        plt.plot_size(height=20)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))

        plt.show()

    @staticmethod
    def missed_moves_pair(algorithm: Algorithm) -> list[Algorithm, Algorithm]:
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
    def score(self) -> float:
        if not self.method_applied:
            return None

        bonus = max((30 - (self.time / SECOND)) / 5, 0)
        malus = 0
        malus += self.execution_missed_moves
        malus += self.transition_missed_moves * 0.5

        final_score = self.method_applied.score - malus + bonus
        return min(max(0, final_score), 20)

    @cached_property
    def link(self) -> str:
        date = self.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        return self.alg_cubing_url(
            f'Solve { date }: { format_time(self.time) }'.replace(' ', '%20'),
            self.scramble,
            self.reconstruction_alg_cubing,
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
    def as_save(self) -> dict:
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
