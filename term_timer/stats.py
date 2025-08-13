from functools import cached_property

import numpy as np
import plotext as plt
from rich import box
from rich.table import Table

from term_timer.config import STATS_CONFIG
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SECOND_BINS
from term_timer.constants import STEP_BAR
from term_timer.formatter import compute_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_grade
from term_timer.formatter import format_score
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.magic_cube import Cube
from term_timer.solve import Solve


class StatisticsTools:
    def __init__(self, stack: list[Solve]):
        self.stack = stack
        self.stack_time = [
            s.final_time for s in stack
        ]
        self.stack_time_sorted = sorted(
            [s for s in self.stack_time if s],
        )

    @staticmethod
    def mo(limit: int, stack_elapsed: list[int]) -> int:
        if limit > len(stack_elapsed):
            return -1

        return int(np.mean(stack_elapsed[-limit:]))

    @staticmethod
    def ao(limit: int, stack_elapsed: list[int]) -> int:
        if limit > len(stack_elapsed):
            return -1

        cap = int(np.ceil(limit * 5 / 100))

        last_of = stack_elapsed[-limit:]
        for _ in range(cap):
            last_of.remove(min(last_of))
            last_of.remove(max(last_of))

        return int(np.mean(last_of))

    def best_mo(self, limit: int) -> int:
        mos: list[int] = []
        stack = list(self.stack_time[:-1])

        current_mo = getattr(self, f'mo{ limit }')
        if current_mo:
            mos.append(current_mo)

        while 42:
            mo = self.mo(limit, stack)
            if mo == -1:
                break
            if mo:
                mos.append(mo)
            stack.pop()

        if mos:
            return min(mos)
        return 0

    def best_ao(self, limit: int) -> int:
        aos: list[int] = []
        stack = list(self.stack_time[:-1])

        current_ao = getattr(self, f'ao{ limit }')
        if current_ao:
            aos.append(current_ao)

        while 42:
            ao = self.ao(limit, stack)
            if ao == -1:
                break
            if ao:
                aos.append(ao)
            stack.pop()

        if aos:
            return min(aos)
        return 0


class Statistics(StatisticsTools):

    @cached_property
    def bpa(self) -> int:
        if self.stack_time_sorted:
            return int(np.mean(self.stack_time_sorted[:3]))
        return 0

    @cached_property
    def wpa(self) -> int:
        if self.stack_time_sorted:
            return int(np.mean(self.stack_time_sorted[-3:]))
        return 0

    @cached_property
    def mo3(self) -> int:
        return self.mo(3, self.stack_time)

    @cached_property
    def ao5(self) -> int:
        return self.ao(5, self.stack_time)

    @cached_property
    def ao12(self) -> int:
        return self.ao(12, self.stack_time)

    @cached_property
    def ao100(self) -> int:
        return self.ao(100, self.stack_time)

    @cached_property
    def ao1000(self) -> int:
        return self.ao(1000, self.stack_time)

    @cached_property
    def best_mo3(self) -> int:
        return self.best_mo(3)

    @cached_property
    def best_ao5(self) -> int:
        return self.best_ao(5)

    @cached_property
    def best_ao12(self) -> int:
        return self.best_ao(12)

    @cached_property
    def best_ao100(self) -> int:
        return self.best_ao(100)

    @cached_property
    def best_ao1000(self) -> int:
        return self.best_ao(1000)

    @cached_property
    def best(self) -> int:
        if self.stack_time_sorted:
            return self.stack_time_sorted[0]
        return 0

    @cached_property
    def worst(self) -> int:
        if self.stack_time_sorted:
            return self.stack_time_sorted[-1]
        return 0

    @cached_property
    def mean(self) -> int:
        return int(np.mean(self.stack_time))

    @cached_property
    def median(self) -> int:
        return int(np.median(self.stack_time))

    @cached_property
    def stdev(self) -> int:
        return int(np.std(self.stack_time))

    @cached_property
    def delta(self) -> int:
        return (
            self.stack[-1].time
            - self.stack[-2].time
        )

    @cached_property
    def total(self) -> int:
        return len(self.stack)

    @cached_property
    def total_time(self) -> int:
        return sum(self.stack_time)

    @cached_property
    def advanced_solves(self) -> int:
        return sum(1 for s in self.stack if s.advanced) / self.total

    @cached_property
    def score(self) -> int:
        return sum(s.score for s in self.stack if s.advanced) / self.total

    @cached_property
    def repartition(self) -> list[tuple[int, int]]:
        gap = (self.worst - self.best) / SECOND

        best_bin = STATS_CONFIG.get('distribution')
        if not best_bin:
            for second in SECOND_BINS:
                if gap / 10 < second:
                    best_bin = second
                    break

        values = [st / SECOND for st in self.stack_time_sorted]

        min_val = int((np.min(values) // best_bin) * best_bin)
        max_val = int(((np.max(values) // best_bin) + 1) * best_bin)

        bins = np.arange(
            int(min_val),
            int(max_val + best_bin),
            best_bin,
        )

        (histo, bin_edges) = np.histogram(values, bins=bins)

        return [
            (value, edge)
            for value, edge in zip(histo, bin_edges, strict=False)
            if value
        ]


class StatisticsReporter(Statistics):

    def __init__(self, cube_size: int, stack: list[Solve]):
        self.cube_size = cube_size
        self.cube_name = f'{ cube_size }x{ cube_size }x{ cube_size }'

        super().__init__(stack)

    def resume(self, prefix: str = '', *, show_title: bool = False) -> None:
        if show_title:
            console.print(
                f'[title]Statistics for { self.cube_name }[/title]',
            )

        console.print(
            f'[stats]{ prefix }Total :[/stats]',
            f'[result]{ self.total }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Time  :[/stats]',
            f'[result]{ format_time(self.total_time) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Mean  :[/stats]',
            f'[result]{ format_time(self.mean) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Median:[/stats]',
            f'[result]{ format_time(self.median) }[/result]',
        )
        console.print(
            f'[stats]{ prefix }Stdev :[/stats]',
            f'[result]{ format_time(self.stdev) }[/result]',
        )
        if self.total >= 2:
            if self.total >= 3:
                console.print(
                    f'[stats]{ prefix }Best  :[/stats]',
                    f'[green]{ format_time(self.best) }[/green]',
                    '[stats]BPA  :[/stats]',
                    f'[result]{ format_time(self.bpa) }[/result]',
                    format_delta(self.bpa - self.best),
                )
                console.print(
                    f'[stats]{ prefix }Worst :[/stats]',
                    f'[red]{ format_time(self.worst) }[/red]',
                    '[stats]WPA  :[/stats]',
                    f'[result]{ format_time(self.wpa) }[/result]',
                    format_delta(self.wpa - self.worst),
                )
            else:
                console.print(
                    f'[stats]{ prefix }Best  :[/stats]',
                    f'[green]{ format_time(self.best) }[/green]',
                )
                console.print(
                    f'[stats]{ prefix }Worst :[/stats]',
                    f'[red]{ format_time(self.worst) }[/red]',
                )
        if self.total >= 3:
            console.print(
                f'[stats]{ prefix }Mo3   :[/stats]',
                f'[mo3]{ format_time(self.mo3) }[/mo3]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_mo3) }[/result]',
                format_delta(self.mo3 - self.best_mo3),
            )
        if self.total >= 5:
            console.print(
                f'[stats]{ prefix }Ao5   :[/stats]',
                f'[ao5]{ format_time(self.ao5) }[/ao5]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao5) }[/result]',
                format_delta(self.ao5 - self.best_ao5),
            )
        if self.total >= 12:
            console.print(
                f'[stats]{ prefix }Ao12  :[/stats]',
                f'[ao12]{ format_time(self.ao12) }[/ao12]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao12) }[/result]',
                format_delta(self.ao12 - self.best_ao12),
            )
        if self.total >= 100:
            console.print(
                f'[stats]{ prefix }Ao100 :[/stats]',
                f'[ao100]{ format_time(self.ao100) }[/ao100]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao100) }[/result]',
                format_delta(self.ao100 - self.best_ao100),
            )
        if self.total >= 1000:
            console.print(
                f'[stats]{ prefix }Ao1000:[/stats]',
                f'[ao1000]{ format_time(self.ao1000) }[/ao1000]',
                '[stats]Best :[/stats]',
                f'[result]{ format_time(self.best_ao1000) }[/result]',
                format_delta(self.ao1000 - self.best_ao1000),
            )

        if self.total > 1:
            max_count = compute_padding(
                max(c for c, e in self.repartition),
            )

            max_edge = max(e for c, e in self.repartition)
            total_percent = 0.0
            for count, edge in self.repartition:
                percent = (count / self.total)
                total_percent += percent

                start = f'[stats]{ count!s:{" "}>{max_count}} '
                start += f'([edge]{ format_edge(edge, max_edge) }[/edge])'
                start = start.ljust(26 + len(prefix))

                console.print(
                    f'{ start }:[/stats]',
                    f'[bar]{ round(percent * STEP_BAR) * " " }[/bar]'
                    f'{ (STEP_BAR - round(percent * STEP_BAR)) * " " }'
                    f'[result]{ percent * 100:05.2f}%[/result]   ',
                    f'[percent]{ total_percent * 100:05.2f}%[/percent]',
                )

    def listing(self, limit: int, sorting: str) -> None:
        console.print(
            f'[title]Listing for { self.cube_name }[/title]',
        )

        size = len(self.stack)
        max_count = compute_padding(size) + 1

        if not limit:
            s = slice(None, None)
        elif limit > 0:
            s = slice(None, limit)
        else:
            s = slice(limit, None)

        indexed_solves = [
            (size - i, self.stack[size - (i + 1)])
            for i in range(size)
        ]

        indices = range(*s.indices(size))

        if sorting == 'time':
            indexed_solves.sort(key=lambda x: x[1].time)

        for indice in indices:
            original_index, solve = indexed_solves[indice]
            index = f'#{ original_index }'
            date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

            header = f'[stats]{ index:{" "}>{max_count}}[/stats]'
            if solve.advanced:
                header = (
                    f'[localhost][link={ solve.link_term_timer }]'
                    f'{ index:{" "}>{max_count}}'
                    '[/link][/localhost]'
                )

            time_class = 'result'
            if solve.time == self.best:
                time_class = 'success'
            elif solve.time == self.worst:
                time_class = 'warning'

            flag_class = 'result'
            if solve.flag == DNF:
                flag_class = 'dnf'
            if solve.flag == PLUS_TWO:
                flag_class = 'plus-two'

            console.print(
                header,
                f'[{ time_class }]{ format_time(solve.time) }[/{ time_class }]',
                f'[date]{ date }[/date]',
                f'[consign]{ solve.scramble }[/consign]',
                f'[{ flag_class }]{ solve.flag }[/{ flag_class }]',
            )

    def detail(self, solve_id: int, method: str,
               *,
               show_cube: bool,
               show_reconstruction: bool,
               show_tps_graph: bool,
               show_time_graph: bool,
               show_recognition_graph: bool) -> None:
        try:
            solve = self.stack[solve_id - 1]
        except IndexError:
            console.print(
                f'Invalid solve #{ solve_id }',
                style='warning',
            )
            return

        solve.method_name = method

        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        console.print(
            f'[title]Detail for { self.cube_name } #{ solve_id }[/title]',
        )
        console.print(
            '[stats]Time       :[/stats] '
            f'[time]{ format_time(solve.time) }[/time]'
            f'[result]{ solve.flag }[/result]',
        )
        console.print(
            '[stats]Date       :[/stats] '
            f'[date]{ date }[/date]',
        )
        console.print(
            '[stats]Session    :[/stats] '
            f'[session]{ solve.session.title() }[/session]',
        )
        if solve.device:
            console.print(
                '[stats]Cube       :[/stats] '
                f'[device]{ solve.device }[/device]',
            )
        if solve.timer:
            console.print(
                '[stats]Timer      :[/stats] '
                f'[timer]{ solve.timer }[/timer]',
            )

        if solve.advanced:
            grade = format_grade(solve.score)
            grade_class = grade.lower()
            grade_line = (
                f' [grade_{ grade_class }]'
                f'{ grade:<2}'
                f'[/grade_{ grade_class }]'
                f' { format_score(solve.score) }'
            )
            console.print(f'[stats]Grade      :[/stats]{ grade_line }')

            grade = format_grade(solve.method_applied.score)
            grade_class = grade.lower()
            grade_line = (
                f' [grade_{ grade_class }]'
                f'{ grade:<2}'
                f'[/grade_{ grade_class }]'
                f' { format_score(solve.method_applied.score) }'
            )
            console.print(
                f'[stats]Grade { solve.method_analyser.name:<5}:[/stats]'
                f'{ grade_line }',
            )

            recognition_time = format_time(
                solve.recognition_time,
                allow_dnf=False,
            )
            recog_percent = solve.recognition_time / solve.time * 100.0
            recog_class = solve.method_applied.normalize_value(
                'solve', 'recognition',
                recog_percent, 'recognition-p',
            )
            console.print(
                '[stats]Recognition:[/stats] '
                f'[result]{ recognition_time }[/result]'
                f' [{ recog_class }]{ recog_percent:.2f}%[{ recog_class }]',
            )

            execution_time = format_time(
                solve.execution_time,
                allow_dnf=False,
            )
            exec_percent = solve.execution_time / solve.time * 100.0
            exec_class = solve.method_applied.normalize_value(
                'solve', 'execution',
                exec_percent, 'execution-p',
            )
            console.print(
                '[stats]Execution  :[/stats] '
                f'[result]{ execution_time }[/result]'
                f' [{ exec_class }]{ exec_percent:.2f}%[{ exec_class }]',
            )

            metric_string = '[stats]Metrics    :[/stats] '
            for metric in STATS_CONFIG.get('metrics'):
                value = solve.reconstruction.metrics[metric]
                metric_string += (
                    f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
                )
            metric_string += f'[tps]{ solve.tps:.2f} TPS[/tps] '

            console.print(metric_string)

            missed_string = '[stats]Overhead   :[/stats] '
            all_missed_moves = solve.all_missed_moves
            execution_missed_moves = solve.execution_missed_moves
            transition_missed_moves = solve.transition_missed_moves
            if all_missed_moves:
                missed_string += (
                    f'[warning]{ all_missed_moves } QTM[/warning]'
                )
                if execution_missed_moves:
                    missed_string += (
                        ' [exec-overhead]'
                        f'(+{ execution_missed_moves } execution)'
                        '[/exec-overhead]'
                    )
                if transition_missed_moves:
                    missed_string += (
                        ' [trans-overhead]'
                        f'(+{ transition_missed_moves } transition)'
                        '[/trans-overhead]'
                    )
            else:
                missed_string += '[success]Optimal execution[/success]'

            console.print(missed_string)

            pauses_string = '[stats]Pauses     :[/stats] '
            if solve.execution_pauses:
                pauses_string += (
                    f'[caution]{ solve.execution_pauses }[/caution]'
                )
            else:
                pauses_string += '[success]None[/success]'

            console.print(pauses_string)

            aufs_string = '[stats]Adjusts UF :[/stats] '
            if solve.aufs > 5:
                aufs_string += (
                    f'[warning]{ solve.aufs }[/warning]'
                )
            elif solve.aufs > 2:
                aufs_string += (
                    f'[caution]{ solve.aufs }[/caution]'
                )
            elif solve.aufs:
                aufs_string += (
                    f'[success]{ solve.aufs }[/success]'
                )
            else:
                aufs_string += '[success]None[/success]'

            console.print(aufs_string)

        console.print(
            '[stats]Scramble   :[/stats] '
            f'[consign]{ solve.scramble }[/consign]',
        )
        if show_cube:
            cube = Cube(self.cube_size)
            cube.rotate(solve.scramble)

            console.print(cube.full_cube(None), end='')

        if solve.advanced:
            if show_reconstruction:
                console.print(
                    '[title]Reconstruction '
                    f'{ solve.method_analyser.name }[/title]',
                    f'[localhost][link={ solve.link_term_timer }]'
                    'Term-Timer[/link][/localhost]',
                    f'[algcubing][link={ solve.link_alg_cubing }]'
                    'alg.cubing.net[/link][/algcubing]',
                    f'[cubedb][link={ solve.link_cube_db }]'
                    'cubedb.net[/link][/cubedb]',
                )
                console.print(solve.method_line, end='')
            if show_time_graph:
                solve.time_graph()
            if show_tps_graph:
                solve.tps_graph()
            if show_recognition_graph:
                solve.recognition_graph()

    def case_table(self, title, items, sorting, ordering):
        table = Table(title=f'{ title }s', box=box.SIMPLE)
        table.add_column('Case', width=10)
        table.add_column('Σ', width=3)
        table.add_column('Freq.', width=5, justify='right')
        table.add_column('Prob.', width=5, justify='right')
        table.add_column('Reco.', width=5, justify='right')
        table.add_column('Exec.', width=5, justify='right')
        table.add_column('Time', width=5, justify='right')
        table.add_column('Ao12', width=5, justify='right')
        table.add_column('Ao5', width=5, justify='right')
        table.add_column('QTM', width=5, justify='right')
        table.add_column('TPS', width=5, justify='right')
        table.add_column('eTPS', width=5, justify='right')

        for name, info in sorted(
                items.items(),
                key=lambda x: (x[1][sorting], x[0]),
                reverse=ordering == 'desc',
        ):
            percent_klass = (
                info['frequency'] > info['probability'] and 'green'
            ) or 'red'

            label = f'{ title } { name.split(" ")[0] }'
            head = (
                '[cubingfache][link=https://cubing.fache.fr/'
                f'{ title }/{ name.split(" ")[0] }.html]{ label }'
                '[/link][/cubingfache]'
            )

            if 'SKIP' in name:
                head = f'[skipped]{ name }[/skipped]'

            count = info['count']

            table.add_row(
                head,
                f'[stats]{ count!s }[/stats]',
                f'[{ percent_klass }]'
                f'{ (info["frequency"] * 100):.2f}%'
                f'[/{ percent_klass }]',
                '[percent]'
                f'{ (info["probability"] * 100):.2f}%'
                '[/percent]',
                '[recognition]' +
                format_duration(info['recognition']) +
                '[/recognition]',
                '[execution]' +
                format_duration(info['execution']) +
                '[/execution]',
                '[duration]' +
                format_duration(info['time']) +
                '[/duration]',
                '[ao12]' +
                format_duration(info['ao12']) +
                '[/ao12]',
                '[ao5]' +
                format_duration(info['ao5']) +
                '[/ao5]',
                f'[moves]{ info["qtm"]:.2f}[/moves]',
                f'[tps]{ info["tps"]:.2f}[/tps]',
                f'[tps-e]{ info["etps"]:.2f}[/tps-e]',
            )
        console.print(table)

    def cfop(self, analyses, *, oll_only: bool = False, pll_only: bool = False,
             sorting: str = 'count', ordering: str = 'asc') -> None:
        if sorting == 'case':
            sorting = 'label'

        if not pll_only:
            self.case_table('OLL', analyses['resume']['oll'], sorting, ordering)
        if not oll_only:
            self.case_table('PLL', analyses['resume']['pll'], sorting, ordering)

        mean = analyses['mean']
        grade = format_grade(mean)
        grade_class = grade.lower()
        grade_line = (
                f' [grade_{ grade_class }]'
                f'{ grade }'
                f'[/grade_{ grade_class }]'
            )
        console.print(
            f'[title]Grade CFOP :[/title]{ grade_line } ({ mean:.2f})',
        )

    def graph(self) -> None:
        ao5s = []
        ao12s = []
        times = []

        plt.clear_figure()

        for time in self.stack_time:
            seconds = time / SECOND
            times.append(seconds)

            ao5 = self.ao(5, times)
            ao12 = self.ao(12, times)
            ao5s.append((ao5 > 0 and ao5) or None)
            ao12s.append((ao12 > 0 and ao12) or None)

        plt.plot(
            times,
            marker='fhd',
            label='Time',
        )

        if any(ao5s):
            plt.plot(
                ao5s,
                marker='fhd',
                label='AO5',
                color='red',
            )

        if any(ao12s):
            plt.plot(
                ao12s,
                marker='fhd',
                label='AO12',
                color='blue',
            )

        plt.title(f'Tendencies { self.cube_name }')
        plt.plot_size(height=25)

        plt.canvas_color('default')
        plt.axes_color('default')
        plt.ticks_color((0, 175, 255))
        plt.ticks_style('bold')

        plt.show()
