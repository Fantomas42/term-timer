"""Tools command."""
from argparse import Namespace

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.annotations import ListingFilters
from term_timer.in_out import load_all_solves
from term_timer.interface.console import console
from term_timer.interface.terminal import Terminal
from term_timer.stats import SolveStatisticsReporter


def tools(command: str, options: Namespace) -> int:
    """
    Execute tool commands.

    Returns:
        Exit code (0 for success, 1 if no saved solves).

    """
    cube = options.cube

    stack = load_all_solves(
        cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )

    session_stats = SolveStatisticsReporter(
        cube,
        stack,
    )

    if not session_stats.stack:
        console.print(
            f'🤔 No saved solves yet for { session_stats.cube_name }'
            ' matching requirements.',
            style='warning',
        )
        return 1

    if command == 'list':
        filters = ListingFilters(
            with_comments=options.with_comments,
            without_comments=options.without_comments,
            connected=options.connected,
            unconnected=options.unconnected,
            dnf=options.dnf,
            plus_two=options.plus_two,
            no_penalty=options.no_penalty,
            search_comment=options.search_comment,
            search_scramble=options.search_scramble,
            min_time=options.min_time,
            max_time=options.max_time,
        )
        session_stats.listing(options.count, options.sort, filters)

    if command == 'stats':
        session_stats.resume('Global ', show_title=True)

    if command == 'graph':
        session_stats.graph()

    if command == 'cfop':
        console.print('Aggregating cases...', end='')

        analyses = SolvesMethodAggregator('cfop', stack, full=False).results

        Terminal.clear_line(full=False)

        session_stats.cfop(
            analyses,
            oll_only=options.oll,
            pll_only=options.pll,
            sorting=options.sort,
            ordering=options.order,
        )

    if command == 'detail':
        for solve_id in options.solves:
            session_stats.detail(
                solve_id,
                options.method,
                options.orientation,
                disable_rotations=options.disable_rotations,
                show_highlights=options.show_highlights,
                show_cube=options.show_cube,
                show_reconstruction=options.show_reconstruction,
                show_tps_graph=options.show_tps_graph,
                show_time_graph=options.show_time_graph,
                show_fluency_graph=options.show_fluency_graph,
                show_recognition_graph=options.show_recognition_graph,
            )

    return 0
