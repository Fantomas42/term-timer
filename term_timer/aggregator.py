import logging
import time
from functools import partial
from multiprocessing import Pool
from multiprocessing import cpu_count

from term_timer.methods import get_method_analyser
from term_timer.solve import Solve
from term_timer.stats import StatisticsTools

logger = logging.getLogger(__name__)


def analyse_solve_worker(solve, method_name, *, full=False):
    if not solve.advanced:
        return {
            'solve': solve if full else None,
        }

    solve.method_name = method_name

    if full:
        _ = solve.score

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
        'solve': solve if full else None,
    }


class SolvesMethodAggregator:

    def __init__(self, method_name, stack, *, full=True):
        self.stack = stack
        self.full = full

        self.method_name = method_name
        self.analyser = get_method_analyser(self.method_name)

        self.results = self.aggregate()

    def collect_analyses(self):
        num_processes = max(1, cpu_count() - 1)

        worker_func = partial(
            analyse_solve_worker,
            method_name=self.method_name,
            full=self.full,
        )

        with Pool(processes=num_processes) as pool:
            return pool.map(worker_func, self.stack)

    def aggregate(self):
        start = time.time()
        analyses = self.collect_analyses()

        msg = (
            f'Aggregating { len(self.stack) } '
            f'solves in { (time.time() - start):.3f}s'
        )
        logger.info(msg)

        score = 0
        total = 0
        resume = {}
        stack = []

        for analyse in analyses:
            stack.append(analyse['solve'])

            if 'score' not in analyse:
                continue

            total += 1
            score += analyse['score']

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
            for info in step_cases.values():
                count = len(info['times'])
                info['count'] = count
                info['frequency'] = count / total
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
