from datetime import datetime
from datetime import timezone
from functools import cached_property

import plotext as plt
from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.optimize import optimize_do_undo_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.optimize import optimize_repeat_three_moves
from cubing_algs.transform.optimize import optimize_triple_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.timing import untime_moves

from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import SERVER_CONFIG
from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_cubing_url
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_cube_db_url
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.methods import get_method_analyser
from term_timer.methods.base import get_step_config
from term_timer.transform import prettify_moves
from term_timer.transform import reorient_moves


class Solve:
    def __init__(self,
                 date: int, time: int,
                 scramble: Algorithm | str,
                 flag: str = '',
                 timer: str = '',
                 device: str = '',
                 session: str = '',
                 solve_id: int = 0,
                 cube_size: int = 3,
                 moves: str | None = None):
        self.date = int(date)
        self.time = int(time)
        self.flag = flag
        self.timer = timer
        self.device = device

        self.session = session or 'default'
        self.solve_id = solve_id
        self.cube_size = cube_size

        self.raw_moves = moves
        self.raw_scramble = scramble

        self.method_name = CUBE_METHOD
        self.orientation = CUBE_ORIENTATION

    @cached_property
    def solution(self):
        return parse_moves(self.raw_moves)

    @cached_property
    def scramble(self):
        if not isinstance(self.raw_scramble, Algorithm):
            return parse_moves(self.raw_scramble)
        return self.raw_scramble

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
        return [[m.untimed, m.timed] for m in self.solution]

    @cached_property
    def advanced(self):
        return bool(self.raw_moves)

    @staticmethod
    def compute_tps(moves: int, time: int) -> float:
        if not time:
            return 0

        return moves / (time / SECOND)

    @cached_property
    def reconstruction(self) -> list[str]:
        return prettify_moves(
            reorient_moves(self.orientation, self.solution),
        )

    @cached_property
    def tps(self) -> float:
        return self.compute_tps(len(self.solution), self.time)

    @cached_property
    def aufs(self) -> int:
        return sum(
            (s['aufs'][0] or 0) + (s['aufs'][1] or 0)
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def all_missed_moves(self) -> int:
        return self.missed_moves(self.solution)

    @cached_property
    def step_missed_moves(self) -> int:
        return sum(
            self.missed_moves(s['moves'])
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def step_pauses(self) -> int:
        return sum(
            self.pauses(s['moves'])
            for s in self.method_applied.summary
            if s['type'] != 'virtual'
        )

    @cached_property
    def execution_pauses(self) -> int:
        return self.step_pauses

    @cached_property
    def execution_missed_moves(self) -> int:
        return self.step_missed_moves

    @cached_property
    def transition_missed_moves(self) -> int:
        return self.all_missed_moves - self.step_missed_moves

    @cached_property
    def method_analyser(self):
        return get_method_analyser(
            self.method_name,
        )

    @cached_property
    def method_applied(self) -> dict[str, dict]:
        if not self.advanced:
            return None

        return self.method_analyser(self.scramble, self.solution)

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
    def pause_threshold(self) -> float:
        return self.move_speed * PAUSE_FACTOR

    @cached_property
    def report_line(self) -> str:
        if not self.advanced:
            return ''

        metric_string = ''
        metrics = STATS_CONFIG.get('metrics')
        for metric in metrics:
            value = self.reconstruction.metrics[metric]
            metric_string += (
                f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
            )

        missed_moves = self.all_missed_moves
        missed_line = (
            '[exec-overhead]'
            f'{ missed_moves } missed QTM'
            '[/exec-overhead]'
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

        if self.execution_pauses:
            pause_line = (
                f' [caution]{ self.execution_pauses } Pauses[/caution]'
            )
        else:
            pause_line = ' [success]No Pauses[/success]'

        return (
            f'{ metric_string }'
            f'[tps]{ self.tps:.2f} TPS[/tps] '
            f'{ missed_line }{ pause_line }{ grade_line }'
        )

    @cached_property
    def method_line(self) -> str:
        if not self.method_applied:
            return ''

        line = (
            '[step]Orientation:[/step] '
            f'[consign]{ self.orientation!s }[/consign]\n'
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
                    self.reconstruction_step_line(info, multiple=False) +
                    '[/consign]'
                )
                if info['cases'] and info['cases'][0]:
                    aufs = ''
                    if info['aufs'][0]:
                        aufs += f' +{ info["aufs"][0] } pre-AUF'
                    if info['aufs'][1]:
                        aufs += f' +{ info["aufs"][1] } post-AUF'

                    if info['name'] in {'OLL', 'PLL'}:
                        link = (
                            'https://cubing.fache.fr/'
                            f'{ info["name"] }/'
                            f'{ info["cases"][0].split(" ")[0] }.html'
                        )
                        footer += (
                            ' [comment]// '
                            f'[link={ link }]{ info["cases"][0] }[/link]'
                            f'{ aufs }[/comment]'
                        )
                    else:
                        footer += (
                            ' [comment]// ' +
                            ' '.join(info['cases']) + aufs +
                            '[/comment]'
                        )

            move_klass = self.method_applied.normalize_value(
                'moves', info['name'],
                info['moves_prettified'].metrics['htm'],
                'result',
            )
            percent_klass = self.method_applied.normalize_value(
                'percent', info['name'],
                info['total_percent'],
                'duration-p',
            )

            tps = self.compute_tps(info['qtm'], info['total'])
            if not info['execution']:
                tps_exec = tps
            else:
                tps_exec = self.compute_tps(info['qtm'], info['execution'])

            line += (
                f'{ header }'
                f'[{ move_klass }]'
                f'{ info["moves_prettified"].metrics["htm"]:>2} HTM'
                f'[/{ move_klass }] '
                f'[recognition]'
                f'{ format_duration(info["recognition"]):>5}s[/recognition] '
                f'[recognition-p]'
                f'{ info["recognition_percent"]:5.2f}%[/recognition-p] '
                f'[execution]'
                f'{ format_duration(info["execution"]):>5}s[/execution] '
                f'[execution-p]'
                f'{ info["execution_percent"]:5.2f}%[/execution-p] '
                f'[duration]'
                f'{ format_duration(info["total"]):>5}s[/duration] '
                f'[{ percent_klass }]'
                f'{ info["total_percent"]:5.2f}%[/{ percent_klass }] '
                f'[tps]{ tps:.2f} TPS[/tps] '
                f'[tps-e]{ tps_exec:.2f} eTPS[/tps-e]'
                f'{ footer }\n'
            )

        return line

    def reconstruction_step_line(self, step, *, multiple=False) -> str:
        if not step['moves']:
            return ''

        source, compressed = self.missed_moves_pair(
            step['moves_humanized'],
        )
        source_paused = source.transform(
            pause_moves(
                self.move_speed / MS_TO_NS_FACTOR,
                PAUSE_FACTOR,
                multiple=multiple,
            ),
            untime_moves,
            optimize_double_moves,
        )
        compressed_paused = compressed.transform(
            pause_moves(
                self.move_speed / MS_TO_NS_FACTOR,
                PAUSE_FACTOR,
                multiple=multiple,
            ),
            untime_moves,
            optimize_double_moves,
        )

        return format_alg_pauses(
            format_alg_triggers(
                format_alg_moves(
                    format_alg_aufs(
                        format_alg_diff(
                            source_paused,
                            compressed_paused,
                        ),
                        *step['aufs'],
                    ),
                ),
                get_step_config(step['name'], 'triggers', []),
            ),
            self, step, multiple=multiple,
        )

    def reconstruction_step_text(self, step, *, multiple=False) -> str:
        if not step['moves']:
            return ''

        source_paused = step['moves_humanized'].transform(
            pause_moves(
                self.move_speed / MS_TO_NS_FACTOR,
                PAUSE_FACTOR,
                multiple=multiple,
            ),
            untime_moves,
            optimize_double_moves,
        )

        post = int(step['post_pause'] / self.pause_threshold)
        if post:
            source_paused += f' { PAUSE_CHAR }' * (
                post if multiple else 1
            )

        return str(source_paused)

    @cached_property
    def method_text(self):
        return self.method_text_builder(multiple=True)

    def method_text_builder(self, *, multiple) -> str:
        recons = ''

        if not self.advanced:
            return recons

        if self.orientation:
            recons += f'{ self.orientation!s } // Orientation\n'

        for info in self.method_applied.summary:
            if info['type'] == 'virtual':
                continue

            if info['type'] == 'skipped':
                recons += f'// { info["name"] } SKIPPED\n'
                continue

            cases = ''
            if info['cases'] and info['cases'][0]:
                cases = f' ({ " ".join(info["cases"]) })'

            aufs = ''
            if info['aufs'][0]:
                aufs += f'Pre-AUF: +{ info["aufs"][0] } '
            if info['aufs'][1]:
                aufs += f'Post-AUF: +{ info["aufs"][1] } '
            aufs = aufs.strip()

            moves = self.reconstruction_step_text(
                info, multiple=multiple,
            )
            recons += (
                f'{ moves } // '
                f'{ info["name"] }{ cases } '
                f'Reco: { format_duration(info["recognition"]) }s '
                f'Exec: { format_duration(info["execution"]) }s '
                f'HTM: { info["moves_prettified"].metrics["htm"] } '
                f'{ aufs }\n'
            )

            if info['name'] == 'Full Cube':
                return recons

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
                tps = Solve.compute_tps(s['qtm'], s['total'])
                tpss.append(tps)
                etpss.append(Solve.compute_tps(s['qtm'], s['execution']) - tps)
                labels.append(s['name'])

        plt.stacked_bar(
            labels,
            [tpss, etpss],
            labels=['TPS', 'eTPS'],
            color=[119, 39],
        )
        plt.hline(self.tps, 'red')
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
        compressed = algorithm.transform(
            optimize_do_undo_moves,
            optimize_repeat_three_moves,
            optimize_triple_moves,
            to_fixpoint=True,
        )
        return algorithm, compressed

    def missed_moves(self, algorithm) -> int:
        source, compressed = self.missed_moves_pair(algorithm)

        return source.metrics['qtm'] - compressed.metrics['qtm']

    def pauses(self, algorithm) -> int:
        if not algorithm:
            return 0

        pauses = 0
        threshold = self.pause_threshold / MS_TO_NS_FACTOR
        previous_time = algorithm[0].timed

        for move in algorithm:
            time = move.timed
            if time - previous_time > threshold:
                pauses += 1

            previous_time = time

        return pauses

    @cached_property
    def score(self) -> float:
        if not self.method_applied:
            return None

        bonus = max((30 - (self.time / SECOND)) / 5, 0)
        malus = 0
        malus += self.execution_missed_moves
        malus += self.transition_missed_moves * 0.5
        malus += self.execution_pauses * 0.2

        final_score = self.method_applied.score - malus + bonus

        return min(max(0, final_score), 20)

    @cached_property
    def link_alg_cubing(self) -> str:
        date = self.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        return format_alg_cubing_url(
            f'Solve { date } : { format_time(self.time) }'.replace(' ', '%20'),
            str(self.scramble),
            self.method_text,
        )

    @cached_property
    def link_cube_db(self) -> str:
        date = self.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        return format_cube_db_url(
            f'Solve { date } : { format_time(self.time) }'.replace(' ', '%20'),
            str(self.scramble),
            self.method_text,
        )

    @cached_property
    def link_term_timer(self) -> str:
        domain = SERVER_CONFIG.get('domain', 'localhost')
        port = SERVER_CONFIG.get('port', 8333)

        return (
            f'http://{ domain }:{ port }'
            f'/{ self.cube_size }/{ self.session }/{ self.solve_id }/'
        )

    @cached_property
    def reconstruction_steps_timing(self):
        if not self.advanced:
            return []

        speed = self.move_speed / MS_TO_NS_FACTOR

        timing = []
        previous_time = 0
        orientation_offset = 0

        if CUBE_ORIENTATION:
            orientation_offset = int(CUBE_ORIENTATION.metrics['rtm'] * speed)
            timing.append([0, orientation_offset, str(CUBE_ORIENTATION)])
            previous_time = orientation_offset

        full_algo = ''
        for info in self.method_applied.summary:
            if info['type'] == 'virtual':
                continue
            full_algo += str(info['moves_humanized'])

        moves = parse_moves(full_algo).transform(
            pause_moves(
                self.move_speed / MS_TO_NS_FACTOR,
                PAUSE_FACTOR,
                multiple=False,
            ),
            optimize_double_moves,
        )

        for move in moves:
            time = int(move.timed + orientation_offset + speed)
            starting = max(
                int(time - (speed * (1.6 if move.is_double else 1))),
                previous_time,
            )
            if time - previous_time < 10:
                time = timing[-1][1]
                starting = timing[-1][0]

            timing.append(
                [
                    starting,
                    time,
                    move.untimed,
                ],
            )
            previous_time = time

        return timing

    @property
    def as_save(self) -> dict:
        return {
            'date': self.date,
            'time': self.time,
            'scramble': str(self.scramble),
            'flag': self.flag,
            'timer': self.timer,
            'device': self.device,
            'moves': self.raw_moves or [],
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
