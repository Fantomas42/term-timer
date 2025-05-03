from functools import cached_property
from multiprocessing import Pool
from multiprocessing import cpu_count

import numpy as np
import plotext as plt
from rich import box
from rich.table import Table

from term_timer.config import STATS_CONFIG
from term_timer.console import console
from term_timer.constants import SECOND
from term_timer.constants import SECOND_BINS
from term_timer.constants import STEP_BAR
from term_timer.formatter import computing_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.magic_cube import Cube
from term_timer.methods.cfop import OLL_INFO
from term_timer.methods.cfop import PLL_INFO
from term_timer.methods.cfop import CFOPAnalyser
from term_timer.solve import Solve


class StatisticsTools:
    def __init__(self, stack: list[Solve]):
        self.stack = stack
        self.stack_time = [
            s.final_time for s in stack
        ]
        self.stack_time_sorted = sorted(self.stack_time)

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

        return min(mos)

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

        return min(aos)


class Statistics(StatisticsTools):

    @cached_property
    def bpa(self) -> int:
        return int(np.mean(self.stack_time_sorted[:3]))

    @cached_property
    def wpa(self) -> int:
        return int(np.mean(self.stack_time_sorted[-3:]))

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
    def best(self) -> int:
        return self.stack_time_sorted[0]

    @cached_property
    def worst(self) -> int:
        return self.stack_time_sorted[-1]

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
    def repartition(self) -> list[tuple[int, int]]:
        gap = (self.worst - self.best) / SECOND

        best_bin = STATS_CONFIG.get('distribution')
        if not best_bin:
            for second in SECOND_BINS:
                if gap / 10 < second:
                    best_bin = second
                    break

        values = [st / SECOND for st in self.stack_time]

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

        if self.total > 1:
            max_count = computing_padding(
                max(c for c, e in self.repartition),
            )
            max_edge = max(e for c, e in self.repartition)
            total_percent = 0.0
            for count, edge in self.repartition:
                percent = (count / self.total)
                total_percent += percent

                start = f'[stats]{ count!s:{" "}>{max_count}} '
                start += f'([edge]+{ format_edge(edge, max_edge) }[/edge])'
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
        max_count = computing_padding(size) + 1

        if not limit:
            limit = size

        if sorting == 'time':
            self.stack = sorted(self.stack, key=lambda x: x.time, reverse=True)

        for i in range(limit):
            if i >= size:
                return

            solve = self.stack[size - (i + 1)]
            index = f'#{ size - i}'
            date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

            header = f'[stats]{ index:{" "}>{max_count}}[/stats]'
            if solve.raw_moves:
                header = (
                    f'[extlink][link={ solve.link }]'
                    f'{ index:{" "}>{max_count}}[/link][/extlink]'
                )

            time_class = 'result'
            if solve.time == self.best:
                time_class = 'success'
            elif solve.time == self.worst:
                time_class = 'warning'

            console.print(
                header,
                f'[{ time_class }]{ format_time(solve.time) }[/{ time_class }]',
                f'[date]{ date }[/date]',
                f'[consign]{ solve.scramble }[/consign]',
                f'[result]{ solve.flag }[/result]',
            )

    def detail(self, solve_id: int) -> None:
        try:
            solve = self.stack[solve_id - 1]
        except IndexError:
            console.print(
                f'Invalid solve #{ solve_id }',
                style='warning',
            )
            return

        cube = Cube(self.cube_size)
        cube.rotate(solve.scramble)

        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        console.print(
            f'[title]Detail for { self.cube_name } #{ solve_id }[/title]',
        )
        console.print(
            '[stats]Time       :[/stats] '
            f'[result]{ format_time(solve.time) }[/result]'
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

        if solve.raw_moves:
            grade = format_grade(solve.score)
            grade_class = grade.lower()
            grade_line = (
                f' [grade_{ grade_class }]'
                f'{ grade }'
                f'[/grade_{ grade_class }]'
                f' ({ solve.score:.2f})'
            )
            console.print(f'[stats]Grade      :[/stats]{ grade_line }')

            metric_string = '[stats]Metrics    :[/stats] '
            for metric in STATS_CONFIG.get('metrics'):
                value = solve.reconstructed.metrics[metric]
                metric_string += (
                    f'[{ metric }]{ value } { metric.upper() }[/{ metric }] '
                )
            metric_string += f'[tps]{ solve.reconstructed_tps:.2f} TPS[/tps] '

            missed_moves = solve.all_missed_moves
            missed_line = f'[missed]{ missed_moves } missed moves[/missed]'
            if not missed_moves:
                missed_line = '[green]No missed move[/green]'

            console.print(metric_string + missed_line)

        console.print(
            '[stats]Scramble   :[/stats] '
            f'[consign]{ solve.scramble }[/consign]',
        )
        console.print(cube.printed(None), end='')

        if solve.raw_moves:
            console.print(
                f'[title]Reconstruction { solve.method.name }[/title]',
                '[extlink]'
                f'[link={ solve.link }]alg.cubing.net[/link][/extlink]',
            )
            console.print(solve.method_line, end='')

            plt.scatter(
                [m[1] / 1000 for m in solve.move_times],
                marker='fhd',
                label='Time',
            )

            yticks = []
            xticks = []
            xlabels = []
            for s in solve.method_applied.summary:
                if s['type'] not in {'skipped', 'virtual'}:
                    index = s['index'][-1] + 1
                    plt.vline(index, 'red')
                    xticks.append(index)
                    yticks.append(solve.move_times[index - 1][1] / 1000)
                    xlabels.append(s['name'])

            plt.xticks(xticks, xlabels)
            plt.yticks(yticks)
            plt.plot_size(height=20)
            plt.canvas_color('default')
            plt.axes_color('default')
            plt.ticks_color((0, 175, 255))
            plt.ticks_style('bold')

            plt.show()

    def analyze_solve_cases(self, solve):
        if not solve.raw_moves:
            return None

        analysis = CFOPAnalyser(solve.scramble, solve.move_times)
        oll, pll = analysis.summary[-2:]

        return {
            'oll': {
                'case': oll['cases'][0],
                'time': oll['total'],
                'execution': oll['execution'],
                'inspection': oll['inspection'],
                'moves': len(oll['moves']),
                'tps': Solve.tps(oll['moves'], oll['total']),
                'etps': Solve.tps(oll['moves'], oll['execution']),
            },
            'pll': {
                'case': pll['cases'][0],
                'time': pll['total'],
                'execution': pll['execution'],
                'inspection': pll['inspection'],
                'moves': len(pll['moves']),
                'tps': Solve.tps(pll['moves'], pll['total']),
                'etps': Solve.tps(pll['moves'], pll['execution']),
            },
            'score_cfop': analysis.score,
        }

    def case_table(self, title, items, sorting, ordering):
        table = Table(title=f'{ title }s', box=box.SIMPLE)
        table.add_column('Case', width=10)
        table.add_column('Σ', width=3)
        table.add_column('Freq.', width=5, justify='right')
        table.add_column('Prob.', width=5, justify='right')
        table.add_column('Insp.', width=5, justify='right')
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

            head = (
                '[extlink][link=https://cubing.fache.fr/'
                f'{ title }/{ name.split(" ")[0] }.html]{ info["label"] }'
                '[/link][/extlink]'
            )
            if 'SKIP' in info['label']:
                head = f'[skipped]{ info["label"] }[/skipped]'

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
                '[inspection]' +
                format_duration(info['inspection']) +
                '[/inspection]',
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
                f'[tps_e]{ info["etps"]:.2f}[/tps_e]',
            )
        console.print(table)

    def cfop(self, oll_only: bool = False, pll_only: bool = False,
             sorting: str = 'count', ordering: str = 'asc') -> None:
        console.print('Aggregating cases...', end='')

        if sorting == 'case':
            sorting = 'label'

        num_processes = max(1, cpu_count() - 1)

        with Pool(processes=num_processes) as pool:
            results = pool.map(self.analyze_solve_cases, self.stack)

        olls = {}
        plls = {}
        score_cfop = 0

        for result in results:
            if not result:
                continue

            score_cfop += result['score_cfop']

            oll_case = result['oll']['case']
            olls.setdefault(
                oll_case, {
                    'inspections': [],
                    'executions': [],
                    'times': [],
                    'moves': [],
                    'tpss': [],
                    'etpss': [],
                },
            )
            olls[oll_case]['times'].append(result['oll']['time'])
            olls[oll_case]['executions'].append(result['oll']['execution'])
            olls[oll_case]['inspections'].append(result['oll']['inspection'])
            olls[oll_case]['moves'].append(result['oll']['moves'])
            olls[oll_case]['tpss'].append(result['oll']['tps'])
            olls[oll_case]['etpss'].append(result['oll']['etps'])

            pll_case = result['pll']['case']
            plls.setdefault(
                pll_case,
                {
                    'inspections': [],
                    'executions': [],
                    'times': [],
                    'moves': [],
                    'tpss': [],
                    'etpss': [],
                 },
            )
            plls[pll_case]['times'].append(result['pll']['time'])
            plls[pll_case]['executions'].append(result['pll']['execution'])
            plls[pll_case]['inspections'].append(result['pll']['inspection'])
            plls[pll_case]['moves'].append(result['pll']['moves'])
            plls[pll_case]['tpss'].append(result['pll']['tps'])
            plls[pll_case]['etpss'].append(result['pll']['etps'])

        total = len(results)

        for name, info in olls.items():
            count = len(info['times'])
            info['count'] = count
            info['frequency'] = count / total
            info['probability'] = OLL_INFO[name]['probability']
            info['label'] = f'OLL { name.split(" ")[0] }'
            info['inspection'] = sum(info['inspections']) / count
            info['execution'] = sum(info['executions']) / count
            info['time'] = sum(info['times']) / count
            info['ao5'] = self.ao(5, info['times'])
            info['ao12'] = self.ao(12, info['times'])
            info['qtm'] = sum(info['moves']) / count
            info['tps'] = sum(info['tpss']) / count
            info['etps'] = sum(info['etpss']) / count

        for name, info in plls.items():
            count = len(info['times'])
            info['count'] = count
            info['frequency'] = count / total
            info['probability'] = PLL_INFO[name]['probability']
            info['label'] = f'PLL { name }'
            info['inspection'] = sum(info['inspections']) / count
            info['execution'] = sum(info['executions']) / count
            info['time'] = sum(info['times']) / count
            info['ao5'] = self.ao(5, info['times'])
            info['ao12'] = self.ao(12, info['times'])
            info['qtm'] = sum(info['moves']) / count
            info['tps'] = sum(info['tpss']) / count
            info['etps'] = sum(info['etpss']) / count

        print('\r', end='')

        if not pll_only:
            self.case_table('OLL', olls, sorting, ordering)
        if not oll_only:
            self.case_table('PLL', plls, sorting, ordering)

        mean = score_cfop / total
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
