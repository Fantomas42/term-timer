from datetime import datetime
from datetime import timezone
from functools import cached_property
from typing import TypedDict

import plotext as plt
from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.optimize import optimize_do_undo_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.optimize import optimize_repeat_three_moves
from cubing_algs.transform.optimize import optimize_triple_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.transform.translate import translate_moves

from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import SERVER_CONFIG
from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
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
from term_timer.methods.base import Analyser
from term_timer.methods.base import get_step_config
from term_timer.methods.types import StepSummary
from term_timer.orientation import get_orientation_faces
from term_timer.orientation import get_orientation_moves
from term_timer.transform import prettify_moves


class SolveData(TypedDict):
    """Dictionary representation of a solve for serialization."""
    date: int
    time: int
    scramble: str
    flag: SolveFlag
    timer: str
    device: str
    moves: str


class Solve:
    def __init__(self,
                 date: float, time: int,
                 scramble: Algorithm | str,
                 flag: SolveFlag = '',
                 timer: str = '',
                 device: str = '',
                 session: str = '',
                 solve_id: int = 0,
                 cube_size: int = 3,
                 moves: str | None = None) -> None:
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
    def solution(self) -> Algorithm:
        if self.raw_moves is None:
            return Algorithm()
        return parse_moves(self.raw_moves)

    @cached_property
    def scramble(self) -> Algorithm:
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
    def move_times(self) -> list[tuple[Move, int]]:
        return [(m.untimed, m.timed) for m in self.solution]

    @cached_property
    def advanced(self) -> bool:
        return bool(self.raw_moves)

    @cached_property
    def orientation_faces(self) -> str:
        if self.orientation == 'auto':
            return get_orientation_faces(self.scramble, self.solution)
        return self.orientation

    @cached_property
    def orientation_moves(self) -> Algorithm:
        return get_orientation_moves(self.orientation_faces)

    @staticmethod
    def compute_tps(moves: int, time: int) -> float:
        if not time:
            return 0

        return moves / (time / SECOND)

    @cached_property
    def reconstruction(self) -> Algorithm:
        return prettify_moves(
            translate_moves(self.orientation_moves)(self.solution),
        )

    @cached_property
    def tps(self) -> float:
        return self.compute_tps(len(self.solution), self.time)

    @cached_property
    def aufs(self) -> int:
        if not self.method_applied:
            return 0

        return sum(
            (step['aufs'][0] or 0) + (step['aufs'][1] or 0)
            for step in self.method_applied.summary
            if step['type'] != 'virtual'
        )

    @cached_property
    def all_missed_moves(self) -> int:
        return self.missed_moves(self.solution)

    @cached_property
    def step_missed_moves(self) -> int:
        if not self.method_applied:
            return 0

        return sum(
            self.missed_moves(step['moves'])
            for step in self.method_applied.summary
            if step['type'] != 'virtual'
        )

    @cached_property
    def step_pauses(self) -> int:
        if not self.method_applied:
            return 0

        return sum(
            self.pauses(step['moves'])
            for step in self.method_applied.summary
            if step['type'] != 'virtual'
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
    def method_analyser(self) -> type[Analyser]:
        return get_method_analyser(
            self.method_name,
        )

    @cached_property
    def method_applied(self) -> Analyser | None:
        if not self.advanced:
            return None

        return self.method_analyser(
            self.scramble, self.solution,
            self.orientation_faces,
            self.orientation_moves,
        )

    @cached_property
    def recognition_time(self) -> int:
        if not self.method_applied:
            return 0

        return sum(
            step['recognition']
            for step in self.method_applied.summary
            if step['type'] != 'virtual'
        )

    @cached_property
    def execution_time(self) -> int:
        if not self.method_applied:
            return 0

        return sum(
            step['execution']
            for step in self.method_applied.summary
            if step['type'] != 'virtual'
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
        metrics_dict = self.reconstruction.metrics._asdict()
        for metric in metrics:
            value = metrics_dict[metric]
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

        score = self.score if self.score is not None else 0.0
        grade = format_grade(score)
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

        rotation_line = ''
        if self.rotations:
            pause_line = (
                f' [caution]{ self.rotations } Rotations[/caution]'
            )

        return (
            f'{ metric_string }'
            f'[tps]{ self.tps:.2f} TPS[/tps] '
            f'{ missed_line }{ pause_line }{ rotation_line }{ grade_line }'
        )

    @cached_property
    def trainer_line(self) -> str:
        if not self.advanced:
            return ''

        metric_string = ''
        metrics = STATS_CONFIG.get('metrics')
        metrics_dict = self.reconstruction.metrics._asdict()
        for metric in metrics:
            value = metrics_dict[metric]
            metric_string += (
                f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
            )

        missed_line = ''
        missed_moves = self.all_missed_moves
        if missed_line:
            missed_line = (
                '[exec-overhead]'
                f'{ missed_moves } missed QTM'
                '[/exec-overhead] '
            )

        pause_line = ''
        if self.execution_pauses:
            pause_line = (
                f'[caution]{ self.execution_pauses } Pauses[/caution]'
            )

        rotation_line = ''
        if self.rotations:
            pause_line = (
                f' [caution]{ self.rotations } Rotations[/caution]'
            )

        return (
            f'{ metric_string }'
            f'[tps]{ self.tps:.2f} TPS[/tps] '
            f'{ missed_line }{ pause_line }{ rotation_line }'
        )

    @cached_property
    def method_line(self) -> str:
        if not self.method_applied:
            return ''

        line = ''
        if self.orientation_moves:
            line += (
                '[step]Orientation:[/step] '
                f'[rotation]{ self.orientation_moves!s }[/rotation] '
                f'[comment]// { self.orientation_faces }[/comment]\n'
            )

        step: StepSummary
        for step in self.method_applied.summary:

            header = ''
            if step['type'] == 'substep':
                header += f'[substep]- { step["name"]:<9}:[/substep] '
            else:
                header += f'[step]{ step["name"]:<11}:[/step] '

            if step['type'] == 'skipped':
                line += (
                    f'{ header }[skipped]SKIP[/skipped]\n'
                )
                continue

            footer = ''
            if step['type'] != 'virtual':
                if step['total']:
                    ratio_execution = step['execution'] / step['total'] * 12
                    ratio_recognition = step['recognition'] / step['total'] * 12
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
                    self.reconstruction_step_line(step, multiple=False) +
                    '[/consign]'
                )

                aufs = ''
                if step['aufs'][0]:
                    aufs += f' +{ step["aufs"][0] } pre-AUF'
                if step['aufs'][1]:
                    aufs += f' +{ step["aufs"][1] } post-AUF'

                if step['case']:
                    link = (
                        'https://cubing.fache.fr/'
                        f'{ step["name"].split(" ")[0] }/'
                        f'{ step["case"].split(" ")[0] }.html'
                    )
                    details = ''
                    if step['case_infos']:
                        details += f' { " ".join(step["case_infos"]) }'

                    footer += (
                        ' [comment]// '
                        f'[link={ link }]{ step["case"] }[/link]'
                        f'{ details }{ aufs }[/comment]'
                    )

                elif step['case_infos']:
                    footer += (
                        ' [comment]// ' +
                        ' '.join(step['case_infos']) +
                        f'{ aufs }[/comment]'
                    )

            move_klass = self.method_applied.normalize_value(
                'moves', step['name'],
                step['moves_prettified'].metrics.htm,
                'result',
            )
            percent_klass = self.method_applied.normalize_value(
                'percent', step['name'],
                step['total_percent'],
                'duration-p',
            )

            tps = self.compute_tps(step['qtm'], step['total'])
            if not step['execution']:
                tps_exec = tps
            else:
                tps_exec = self.compute_tps(step['qtm'], step['execution'])

            line += (
                f'{ header }'
                f'[{ move_klass }]'
                f'{ step["moves_prettified"].metrics.htm:>2} HTM'
                f'[/{ move_klass }] '
                f'[recognition]'
                f'{ format_duration(step["recognition"]):>5}s[/recognition] '
                f'[recognition-p]'
                f'{ step["recognition_percent"]:5.2f}%[/recognition-p] '
                f'[execution]'
                f'{ format_duration(step["execution"]):>5}s[/execution] '
                f'[execution-p]'
                f'{ step["execution_percent"]:5.2f}%[/execution-p] '
                f'[duration]'
                f'{ format_duration(step["total"]):>5}s[/duration] '
                f'[{ percent_klass }]'
                f'{ step["total_percent"]:5.2f}%[/{ percent_klass }] '
                f'[tps]{ tps:.2f} TPS[/tps] '
                f'[tps-e]{ tps_exec:.2f} eTPS[/tps-e]'
                f'{ footer }\n'
            )

        return line

    def reconstruction_step_line(self, step: StepSummary,
                                 *, multiple: bool = False) -> str:
        if not step['moves']:
            return ''

        speed = int(self.move_speed / MS_TO_NS_FACTOR)
        source, compressed = self.missed_moves_pair(
            step['moves_humanized'],
        )
        source_paused = source.transform(
            pause_moves(
                speed,
                PAUSE_FACTOR,
                multiple=multiple,
            ),
            untime_moves,
            optimize_double_moves,
        )
        compressed_paused = compressed.transform(
            pause_moves(
                speed,
                PAUSE_FACTOR,
                multiple=multiple,
            ),
            untime_moves,
            optimize_double_moves,
        )

        pre_auf = step['aufs'][0] or 0
        post_auf = step['aufs'][1] or 0

        return format_alg_pauses(
            format_alg_triggers(
                format_alg_moves(
                    format_alg_aufs(
                        format_alg_diff(
                            source_paused,
                            compressed_paused,
                        ),
                        pre_auf,
                        post_auf,
                    ),
                ),
                get_step_config(step['name'], 'triggers', []),
            ),
            self, step, multiple=multiple,
        )

    def reconstruction_step_text(self, step: StepSummary,
                                 *, multiple: bool = False) -> str:
        if not step['moves']:
            return ''

        source_paused = step['moves_humanized'].transform(
            pause_moves(
                int(self.move_speed / MS_TO_NS_FACTOR),
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
    def method_text(self) -> str:
        return self.method_text_builder(multiple=True)

    def method_text_builder(self, *, multiple: bool) -> str:
        recons = ''

        if not self.advanced or not self.method_applied:
            return recons

        if self.orientation_moves:
            recons += (
                f'{ self.orientation_moves!s } '
                f'// Orientation ({ self.orientation_faces })\n'
            )

        step: StepSummary
        for step in self.method_applied.summary:
            if step['type'] == 'virtual':
                continue

            if step['type'] == 'skipped':
                recons += f'// { step["name"] } SKIPPED\n'
                continue

            detail_list = list(step['case_infos'])
            if step['case']:
                detail_list.insert(0, step['case'])

            details = ''
            if detail_list:
                details = f' ({ " ".join(detail_list) })'

            aufs = ''
            if step['aufs'][0]:
                aufs += f'Pre-AUF: +{ step["aufs"][0] } '
            if step['aufs'][1]:
                aufs += f'Post-AUF: +{ step["aufs"][1] } '
            aufs = aufs.strip()

            moves = self.reconstruction_step_text(
                step, multiple=multiple,
            )
            recons += (
                f'{ moves } // '
                f'{ step["name"] }{ details } '
                f'Reco: { format_duration(step["recognition"]) }s '
                f'Exec: { format_duration(step["execution"]) }s '
                f'HTM: { step["moves_prettified"].metrics.htm } '
                f'{ aufs }\n'
            )

            if step['name'] == 'Full Cube':
                return recons

        return recons

    def time_graph(self) -> None:
        if not self.advanced or not self.method_applied:
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
        step: StepSummary
        for step in self.method_applied.summary:
            if step['type'] not in {'skipped', 'virtual'}:
                index = step['index'][-1] + 1
                plt.vline(index, 'red')
                xticks.append(index)
                yticks.append(self.move_times[index - 1][1] / 1000)
                xlabels.append(step['name'])

        plt.xticks(xticks, xlabels)
        plt.yticks(yticks)
        plt.plot_size(height=20)
        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))

        plt.show()

    def tps_graph(self) -> None:
        if not self.advanced or not self.method_applied:
            return

        plt.clear_figure()

        tpss = []
        etpss = []
        labels = []
        step: StepSummary
        for step in self.method_applied.summary:
            if step['type'] not in {'skipped', 'virtual'}:
                tps = Solve.compute_tps(step['qtm'], step['total'])
                tpss.append(tps)
                etpss.append(
                    Solve.compute_tps(step['qtm'], step['execution']) - tps,
                )
                labels.append(step['name'])

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
        if not self.advanced or not self.method_applied:
            return

        plt.clear_figure()

        labels = []
        executions = []
        recognitions = []
        step: StepSummary
        for step in self.method_applied.summary:
            if step['type'] not in {'skipped', 'virtual'}:
                labels.append(step['name'])
                recognitions.append(step['recognition'] / SECOND)
                executions.append(step['execution'] / SECOND)

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
    def missed_moves_pair(algorithm: Algorithm) -> tuple[Algorithm, Algorithm]:
        compressed = algorithm.transform(
            optimize_do_undo_moves,
            optimize_repeat_three_moves,
            optimize_triple_moves,
            to_fixpoint=True,
        )
        return algorithm, compressed

    def missed_moves(self, algorithm: Algorithm) -> int:
        source, compressed = self.missed_moves_pair(algorithm)

        return source.metrics.qtm - compressed.metrics.qtm

    def pauses(self, algorithm: Algorithm) -> int:
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
    def rotations(self) -> int:
        if not self.advanced:
            return 0

        return self.solution.metrics.rotations

    @cached_property
    def score(self) -> float | None:
        if not self.method_applied:
            return None

        bonus = max((30 - (self.time / SECOND)) / 5, 0)
        malus = 0.0
        malus += self.execution_missed_moves
        malus += self.transition_missed_moves * 0.5
        malus += self.execution_pauses * 0.2
        malus += self.rotations * 0.1

        final_score = self.method_applied.score - malus + bonus

        return min(max(0.0, final_score), 20.0)

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
    def reconstruction_steps_timing(self) -> list[tuple[int, int, Move]]:
        if not self.advanced or not self.method_applied:
            return []

        speed = self.move_speed / MS_TO_NS_FACTOR

        timing: list[tuple[int, int, Move]] = []
        orientation_offset = 0

        for move in self.orientation_moves:
            time = int(speed * (1.6 if move.is_double else 1))
            timing.append(
                (
                    orientation_offset,
                    orientation_offset + time,
                    move,
                ),
            )
            orientation_offset += time

        previous_time = orientation_offset

        full_algo = ''
        step: StepSummary
        for step in self.method_applied.summary:
            if step['type'] == 'virtual':
                continue
            full_algo += str(step['moves_humanized'])

        moves = parse_moves(full_algo).transform(
            pause_moves(
                int(speed),
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
                (
                    starting,
                    time,
                    move.untimed,
                ),
            )
            previous_time = time

        return timing

    @property
    def as_save(self) -> SolveData:
        return {
            'date': self.date,
            'time': self.time,
            'scramble': str(self.scramble),
            'flag': self.flag,
            'timer': self.timer,
            'device': self.device,
            'moves': self.raw_moves or '',
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
