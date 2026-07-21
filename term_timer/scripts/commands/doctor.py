"""Doctor command."""
from argparse import Namespace

from term_timer.aggregator import SolvesDoctorAggregator
from term_timer.in_out import load_all_solves
from term_timer.interface.console import console
from term_timer.interface.doctor import DoctorReporter
from term_timer.interface.terminal import Terminal


def doctor(options: Namespace) -> int:
    """
    Aggregate doctor diagnostics over the last solves.

    Builds a report of structural weaknesses from the diagnostics of
    the last connected solves, optionally compared to the previous
    window of the same size.

    Returns:
        Exit code (0 for success, 1 if no diagnosable solves).

    """
    stack = load_all_solves(
        options.cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )
    advanced = [solve for solve in stack if solve.advanced]

    if not advanced:
        console.print(
            '🤔 No connected solves to diagnose'
            ' matching requirements.',
            style='warning',
        )
        return 1

    count = options.count
    window = advanced[-count:]

    console.print('Diagnosing solves...', end='')

    aggregator = SolvesDoctorAggregator(options.method, window)

    previous = None
    if options.trend:
        previous_window = advanced[-2 * count:-count]
        if previous_window:
            previous = SolvesDoctorAggregator(
                options.method, previous_window,
            ).results

    Terminal.clear_line(full=False)

    reporter = DoctorReporter(aggregator.results)
    console.print(reporter.report(previous))

    if options.trend:
        if previous is None:
            console.print(
                'No previous window to compare with.',
                style='warning',
            )
        elif previous['total'] < count:
            console.print(
                f'Trend compared against { previous["total"] } '
                'solves only.',
                style='caution',
            )

    return 0
