"""Solve analysis aggregation with multiprocessing support."""
import logging
import time
from functools import partial
from multiprocessing import Pool
from multiprocessing import cpu_count
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.cases import get_case

from term_timer.methods import get_method_analyser
from term_timer.solve import Solve
from term_timer.stats import StatisticsTools
from term_timer.types import CaseStats
from term_timer.types import CaseStatsAccumulator
from term_timer.types import MethodAnalysis
from term_timer.types import SolveAnalysis
from term_timer.types import StepAnalysis

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser
    from term_timer.methods.types import StepSummary

logger = logging.getLogger(__name__)


def analyse_solve_worker(solve: Solve,
                         method_name: str, *,
                         full: bool = False) -> SolveAnalysis:
    """
    Analyze solve using specified method and return analysis result.

    Returns:
        Dictionary containing steps analysis, score, and optional solve.

    """
    if not solve.advanced:
        return {
            'steps': {},
            'score': 0.0,
            'solve': solve if full else None,
        }

    solve.method_name = method_name

    if full:
        _ = solve.score

    analysis = cast('Analyser', solve.method_applied)

    steps: dict[str, StepAnalysis] = {}
    for step_name, step_index in solve.method_analyser.aggregate.items():
        step: StepSummary = analysis.summary[step_index]
        steps[step_name] = {
            'case': step['case'],
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
    """Aggregates solve analysis results using multiprocessing."""

    def __init__(self, method_name: str, stack: list[Solve],
                 *, full: bool = True) -> None:
        """Initialize aggregator and compute aggregated results."""
        self.stack = stack
        self.full = full

        self.method_name = method_name
        self.analyser = get_method_analyser(self.method_name)

        self.results = self.aggregate()

    def collect_analyses(self) -> list[SolveAnalysis]:
        """
        Collect solve analyses using multiprocessing.

        Returns:
            List of analysis results for each solve.

        """
        num_processes = max(1, cpu_count() - 1)

        worker_func = partial(
            analyse_solve_worker,
            method_name=self.method_name,
            full=self.full,
        )

        with Pool(processes=num_processes) as pool:
            return pool.map(worker_func, self.stack)

    def aggregate(self) -> MethodAnalysis:
        """
        Aggregate solve analyses into method statistics.

        Returns:
            Dictionary with total count, mean score, case statistics, and stack.

        """
        start = time.time()
        analyses = self.collect_analyses()

        msg = (
            f'Aggregating { len(self.stack) } '
            f'solves in { (time.time() - start):.3f}s'
        )
        logger.info(msg)

        score = 0.0
        total = 0
        resume: dict[str, dict[str, CaseStatsAccumulator]] = {}
        stack: list[Solve | None] = []

        for analyse in analyses:
            stack.append(analyse['solve'])

            if not analyse['steps']:
                continue

            total += 1
            score += analyse['score']

            step: StepAnalysis
            for step_name, step in analyse['steps'].items():
                step_case = step['case']
                resume.setdefault(step_name, {})
                if step_case not in resume[step_name]:
                    case_info = get_case(step_name.upper(), step_case)
                    resume[step_name][step_case] = {
                        'recognitions': [],
                        'executions': [],
                        'times': [],
                        'qtms': [],
                        'tpss': [],
                        'etpss': [],
                        'probability': case_info.probability,
                    }

                resume[step_name][step_case]['times'].append(step['time'])
                resume[step_name][step_case]['executions'].append(step['execution'])
                resume[step_name][step_case]['recognitions'].append(step['recognition'])
                resume[step_name][step_case]['qtms'].append(step['qtm'])
                resume[step_name][step_case]['tpss'].append(step['tps'])
                resume[step_name][step_case]['etpss'].append(step['etps'])

        final_resume: dict[str, dict[str, CaseStats]] = {}
        for step_name, step_cases in resume.items():
            final_resume[step_name] = {}
            accumulator: CaseStatsAccumulator
            for case_name, accumulator in step_cases.items():
                count = len(accumulator['times'])
                final_resume[step_name][case_name] = {
                    'count': count,
                    'frequency': count / total,
                    'probability': accumulator['probability'],
                    'recognition': sum(accumulator['recognitions']) / count,
                    'execution': sum(accumulator['executions']) / count,
                    'time': sum(accumulator['times']) / count,
                    'ao5': StatisticsTools.ao(5, accumulator['times']),
                    'ao12': StatisticsTools.ao(12, accumulator['times']),
                    'qtm': sum(accumulator['qtms']) / count,
                    'tps': sum(accumulator['tpss']) / count,
                    'etps': sum(accumulator['etpss']) / count,
                }

        return {
            'total': total,
            'mean': score / total if total else 0,
            'resume': final_resume,
            'stack': stack,
        }
