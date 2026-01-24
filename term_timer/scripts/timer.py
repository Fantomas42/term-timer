"""Main timer application entry point."""
import asyncio
from argparse import Namespace
from contextlib import suppress
from pathlib import Path
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import get_arguments
from term_timer.browse.app import run_browse
from term_timer.config import DEBUG
from term_timer.config_edit.app import run_config_edit
from term_timer.exceptions import InvalidCaseError
from term_timer.importers import Importer
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_scrambles
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.interface.terminal import Terminal
from term_timer.logger import configure_logging
from term_timer.manage import ScrambleManager
from term_timer.manage import SessionManager
from term_timer.manage import SolveManager
from term_timer.server.app import Server
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer
from term_timer.trainer import Trainer
from term_timer.types import ListingFilters


async def timer(options: Namespace) -> int:  # noqa: C901, PLR0912
    """
    Run speedcubing timer with scrambles and solve tracking.

    Returns:
        Exit code (0 for success).

    """
    cube = options.cube

    session_parts = []
    if options.session:
        session_parts.append(options.session)

    scrambles = []
    if options.scrambles_file:
        scrambles_file = Path(options.scrambles_file)
        scrambles = load_scrambles(scrambles_file)
        if not scrambles:
            console.print(
                f'🤔 No scrambles in { scrambles_file.name }.',
                style='warning',
            )
            return 0
        session_parts.append(f'scrambles-{ scrambles_file.stem }')
    elif not options.scramble:
        if options.seed:
            session_parts.append(f'seed-{ options.seed }')
        if options.easy_cross:
            session_parts.append('easy-cross')
        elif options.iterations:
            session_parts.append(f'iterations-{ options.iterations }')

    session = '-'.join(session_parts)

    stack = [] if options.free_play else load_solves(cube, session)

    rng = Random(options.seed) if options.seed else Random()  # noqa: S311

    solves_done = 0

    timer = Timer(
        cube_size=cube,
        iterations=options.iterations,
        easy_cross=options.easy_cross,
        scramble=options.scramble,
        scrambles=scrambles,
        session=session,
        free_play=options.free_play,
        show_cheers=options.show_cheers,
        show_cube=options.show_cube,
        show_reconstruction=options.show_reconstruction,
        show_tps_graph=options.show_tps_graph,
        show_time_graph=options.show_time_graph,
        show_fluency_graph=options.show_fluency_graph,
        show_recognition_graph=options.show_recognition_graph,
        method=options.method,
        orientation=options.orientation,
        countdown=options.countdown,
        metronome=options.metronome,
        stack=stack,
        rng=rng,
    )

    if options.bluetooth:
        await timer.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    try:
        while 42:
            done = await timer.start()

            if done:
                solves_done += 1

                if options.solves and solves_done >= options.solves:
                    break
            else:
                break
    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if timer.bluetooth_interface:
            await timer.bluetooth_disconnect()

    if len(timer.stack) > len(timer.stack_done):
        session_stats = SolveStatisticsReporter(cube, timer.stack)
        session_stats.resume('Session ')

    if len(timer.stack_done) > 1:
        round_stats = SolveStatisticsReporter(cube, timer.stack_done)
        round_stats.resume(
            'Free Play ' if options.free_play else 'Current ',
            'round',
        )

    return 0


async def trainer(options: Namespace) -> int:
    """
    Generate training case.

    Returns:
        Exit code (0 for success).

    """
    active_filters = sum([
        bool(options.case_codes),
        options.oldest > 0,
        options.slowest > 0,
    ])
    if active_filters > 1:
        console.print(
            '😱 Only one of --cases, --oldest, or --slowest can be used',
            style='warning',
        )
        return 1

    rng = Random(options.seed) if options.seed else Random()  # noqa: S311

    try:
        trainer = Trainer(
            step=options.step,
            case_codes=options.case_codes,
            oldest=options.oldest,
            slowest=options.slowest,
            free_play=options.free_play,
            orientation=options.orientation,
            show_solution=options.show_solution,
            show_cube=options.show_cube,
            metronome=options.metronome,
            rng=rng,
        )
    except InvalidCaseError as error:
        console.print('😱', str(error), style='warning')
        return 1

    if options.bluetooth:
        await trainer.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    try:
        while 42:
            done = await trainer.start()

            if not done:
                break
    finally:
        if trainer.bluetooth_interface:
            await trainer.bluetooth_disconnect()

    return 0


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
                show_cheers=options.show_cheers,
                show_cube=options.show_cube,
                show_reconstruction=options.show_reconstruction,
                show_tps_graph=options.show_tps_graph,
                show_time_graph=options.show_time_graph,
                show_fluency_graph=options.show_fluency_graph,
                show_recognition_graph=options.show_recognition_graph,
            )

    return 0


def manage(command: str, options: Namespace) -> int:
    """
    Manage solve data.

    Returns:
        Exit code (0 for success).

    """
    if command == 'index':
        session_manager = SessionManager()
        session_manager.index()
        return 0

    if command == 'merge':
        session_manager = SessionManager()
        session_manager.merge(options.sessions)
        return 0

    cube = options.cube

    if command == 'edit':
        if not options.flag and not options.comment:
            console.print(
                '🤔 Nothing to edit, use --flag or --comment at least.',
                style='warning',
            )
            return 0

        for solve_id in options.solves:
            solve_manager = SolveManager(cube, options.session, solve_id)
            solve_manager.display_solve()

            if options.flag:
                solve_manager.update_flag(options.flag, yes=options.yes)
            if options.comment:
                solve_manager.update_comment(options.comment, yes=options.yes)

    if command == 'delete':
        solve_manager = SolveManager(cube, options.session, options.solve)
        solve_manager.display_solve()
        solve_manager.delete()

    if command == 'scramble':
        rng = Random(options.seed) if options.seed else Random()  # noqa: S311

        scramble_manager = ScrambleManager(
            cube_size=cube,
            scrambles=options.scrambles,
            iterations=options.iterations,
            easy_cross=options.easy_cross,
            show_cube=options.show_cube,
            linear=options.linear,
            no_color=options.no_color,
            output_format=options.format,
            seed=options.seed,
            rng=rng,
        )
        scramble_manager.run()

    return 0


def main() -> int:  # noqa: PLR0911
    """
    Run term-timer CLI application.

    Returns:
        Exit code (0 for success).

    """
    configure_logging()

    options = get_arguments()
    command = COMMAND_RESOLUTIONS.get(options.command, options.command)

    with suppress(KeyboardInterrupt):
        if command == 'solve':
            return asyncio.run(timer(options), debug=DEBUG)
        if command == 'train':
            return asyncio.run(trainer(options), debug=DEBUG)
        if command == 'browse':
            asyncio.run(run_browse(), debug=DEBUG)
            return 0
        if command == 'config':
            asyncio.run(run_config_edit(), debug=DEBUG)
            return 0
        if command == 'import':
            return Importer().import_file(options.source)
        if command == 'serve':
            Server().run_server(options.host, options.port, debug=DEBUG)
            return 0
        if command in {'edit', 'delete', 'index', 'merge', 'scramble'}:
            return manage(command, options)
        return tools(command, options)

    return 0
