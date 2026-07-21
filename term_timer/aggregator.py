"""Solve analysis aggregation with multiprocessing support."""
import logging
import time
from functools import partial
from multiprocessing import Pool
from multiprocessing import cpu_count
from typing import TYPE_CHECKING
from typing import cast

from cubing_algs.cases import get_case

from term_timer.annotations import CaseStats
from term_timer.annotations import CaseStatsAccumulator
from term_timer.annotations import DoctorAnalysis
from term_timer.annotations import DoctorReport
from term_timer.annotations import MethodAnalysis
from term_timer.annotations import SolveAnalysis
from term_timer.annotations import StepAnalysis
from term_timer.doctor import aggregate_solve_diagnostics
from term_timer.doctor import generate_solve_diagnostics
from term_timer.methods import get_method_analyser
from term_timer.solve import Solve
from term_timer.stats import StatisticsTools

if TYPE_CHECKING:
    from term_timer.methods.annotations import StepSummary
    from term_timer.methods.base import Analyser

logger = logging.getLogger(__name__)


def analyse_solve_worker(solve: Solve, method_name: str) -> SolveAnalysis:
    """
    Analyze solve using specified method and return analysis result.

    Returns:
        Dictionary containing steps analysis, score, and optional solve.

    """
    if not solve.analysable:
        return {
            'steps': {},
            'score': 0.0,
            'solve': None,
        }

    solve.method_name = method_name
    analysis = cast('Analyser', solve.method_applied)

    summary_by_name = {step['name']: step for step in analysis.summary}
    steps: dict[str, StepAnalysis] = {}
    for step_name, summary_name in solve.method_analyser.aggregate.items():
        step: StepSummary = summary_by_name[summary_name]
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
        'solve': None,
    }


def diagnose_solve_worker(solve: Solve, method_name: str) -> DoctorAnalysis:
    """
    Diagnose solve using specified method and return its diagnostics.

    Returns:
        Dictionary flagging diagnosability and listing diagnostics.

    """
    if not solve.analysable:
        return {
            'diagnosed': False,
            'diagnostics': [],
        }

    solve.method_name = method_name
    if not solve.method_applied:
        return {
            'diagnosed': False,
            'diagnostics': [],
        }

    return {
        'diagnosed': True,
        'diagnostics': generate_solve_diagnostics(solve),
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
        )

        with Pool(processes=num_processes) as pool:
            analyses = pool.map(worker_func, self.stack)

        if self.full:
            for analysis, solve in zip(analyses, self.stack, strict=True):
                analysis['solve'] = solve

        return analyses

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
                    case_info = get_case(step_name, step_case)
                    resume[step_name][step_case] = {
                        'recognitions': [],
                        'executions': [],
                        'times': [],
                        'qtms': [],
                        'tpss': [],
                        'etpss': [],
                        'case': case_info,
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
                    'case': accumulator['case'],
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


class SolvesDoctorAggregator:
    """Aggregates doctor diagnostics across solves using multiprocessing."""

    def __init__(self, method_name: str, stack: list[Solve]) -> None:
        """Initialize aggregator and compute the doctor report."""
        self.stack = stack
        self.method_name = method_name

        self.results = self.aggregate()

    def collect_diagnostics(self) -> list[DoctorAnalysis]:
        """
        Collect solve diagnostics using multiprocessing.

        Returns:
            List of diagnostic results for each solve.

        """
        num_processes = max(1, cpu_count() - 1)

        worker_func = partial(
            diagnose_solve_worker,
            method_name=self.method_name,
        )

        with Pool(processes=num_processes) as pool:
            return pool.map(worker_func, self.stack)

    def aggregate(self) -> DoctorReport:
        """
        Aggregate solve diagnostics into a doctor report.

        Solves that cannot be diagnosed (no reconstruction, no method
        analysis) are excluded from the window: frequencies and impacts
        are relative to the diagnosed solves only.

        Returns:
            Dictionary with diagnosed solve count and sorted findings.

        """
        start = time.time()
        analyses = self.collect_diagnostics()

        msg = (
            f'Diagnosing { len(self.stack) } '
            f'solves in { (time.time() - start):.3f}s'
        )
        logger.info(msg)

        diagnosed = [
            analysis['diagnostics']
            for analysis in analyses
            if analysis['diagnosed']
        ]

        return {
            'total': len(diagnosed),
            'findings': aggregate_solve_diagnostics(diagnosed),
        }
