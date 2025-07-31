import time
from multiprocessing import Pool
from multiprocessing import cpu_count

from term_timer.methods import get_method_analyser
from term_timer.solve import Solve
from term_timer.stats import StatisticsTools


class SolvesMethodAggregator:

    def __init__(self, method_name, stack, *, full=True):
        self.stack = stack
        self.full = full

        self.analyser = get_method_analyser(method_name)
        self.method_name = self.analyser.name

        self.results = self.aggregate()

    def analyse_solve(self, solve: Solve):
        if not solve.advanced:
            return None

        solve.method_name = self.method_name

        if self.full:
            solve.score  # noqa: B018

        analysis = solve.method_applied

        steps = {}
        for step_name, step_index in solve.method_analyser.aggregate.items():
            step = analysis.summary[step_index]
            steps[step_name] = {
                'case': step['cases'][0],
                'time': step['total'],
                'execution': step['execution'],
                'recognition': step['recognition'],
                'qtm': step['qtm'],
                'tps': Solve.compute_tps(step['qtm'], step['total']),
                'etps': Solve.compute_tps(step['qtm'], step['execution']),
            }

        return {
            'steps': steps,
            'score': analysis.score,
            'solve': solve,
        }

    def collect_analyses(self):
        num_processes = max(1, cpu_count() - 1)

        with Pool(processes=num_processes) as pool:
            return pool.map(self.analyse_solve, self.stack)

    def aggregate(self):
        start = time.time()
        analyses = self.collect_analyses()
        print(time.time() - start)

        score = 0
        total = 0
        resume = {}
        stack = []

        for analyse in analyses:
            if not analyse:
                continue

            total += 1
            score += analyse['score']
            stack.append(analyse['solve'])

            for step_name, step in analyse['steps'].items():
                step_case = step['case']
                resume.setdefault(step_name, {})
                resume[step_name].setdefault(
                    step_case, {
                        'recognitions': [],
                        'executions': [],
                        'times': [],
                        'qtms': [],
                        'tpss': [],
                        'etpss': [],
                        'probability': (
                            self.analyser.infos.get(
                                step_name, {},
                            ).get(
                                step_case, {},
                            ).get(
                                'probability', 0,
                            )
                        ),
                    },
                )

                resume[step_name][step_case]['times'].append(step['time'])
                resume[step_name][step_case]['executions'].append(step['execution'])
                resume[step_name][step_case]['recognitions'].append(step['recognition'])
                resume[step_name][step_case]['qtms'].append(step['qtm'])
                resume[step_name][step_case]['tpss'].append(step['tps'])
                resume[step_name][step_case]['etpss'].append(step['etps'])

        for step_cases in resume.values():
            for name, info in step_cases.items():
                count = len(info['times'])
                info['count'] = count
                info['frequency'] = count / total
                info['label'] = f'TODO { name.split(" ")[0] }' #f'OLL { name.split(" ")[0] }'
                info['recognition'] = sum(info['recognitions']) / count
                info['execution'] = sum(info['executions']) / count
                info['time'] = sum(info['times']) / count
                info['ao5'] = StatisticsTools.ao(5, info['times'])
                info['ao12'] = StatisticsTools.ao(12, info['times'])
                info['qtm'] = sum(info['qtms']) / count
                info['tps'] = sum(info['tpss']) / count
                info['etps'] = sum(info['etpss']) / count

        return {
            'total': total,
            'mean': score / total if total else 0,
            'resume': resume,
            'stack': stack,
        }
