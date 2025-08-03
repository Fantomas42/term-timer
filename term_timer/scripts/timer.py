import asyncio
from contextlib import suppress
from random import seed

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import get_arguments
from term_timer.config import DEBUG
from term_timer.importers import Importer
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.interface.terminal import Terminal
from term_timer.logger import configure_logging
from term_timer.manage import SolveManager
from term_timer.scrambler import InvalidCaseError
from term_timer.server.app import Server
from term_timer.stats import StatisticsReporter
from term_timer.timer import Timer
from term_timer.trainer import Trainer


async def timer(options) -> int:
    cube = options.cube

    free_play = options.free_play
    if options.seed or options.iterations or options.easy_cross:
        free_play = True

    stack = [] if free_play else load_solves(cube, options.session)

    if options.seed:
        seed(options.seed)

    solves_done = 0

    timer = Timer(
        cube_size=cube,
        iterations=options.iterations,
        easy_cross=options.easy_cross,
        session=options.session,
        free_play=free_play,
        show_cube=options.show_cube,
        show_reconstruction=options.show_reconstruction,
        show_tps_graph=options.show_tps_graph,
        show_time_graph=options.show_time_graph,
        show_recognition_graph=options.show_recognition_graph,
        countdown=options.countdown,
        metronome=options.metronome,
        stack=stack,
    )

    if options.bluetooth:
        await timer.bluetooth_connect()

    try:
        while 42:
            done = await timer.start()

            if done:
                solves_done += 1

                if options.solves and solves_done >= options.solves:
                    break
            else:
                break
    finally:
        if timer.bluetooth_interface:
            await timer.bluetooth_disconnect()

    if len(timer.stack) > 1:
        session_stats = StatisticsReporter(cube, timer.stack)
        session_stats.resume('Free Play ' if options.free_play else 'Session ')

    return 0


async def trainer(options) -> int:
    trainer = Trainer(
        step=options.step,
        cases=options.case,
        show_cube=options.show_cube,
        metronome=options.metronome,
    )

    if options.bluetooth:
        await trainer.bluetooth_connect()

    try:
        while 42:
            done = await trainer.start()

            if not done:
                break
    except InvalidCaseError as error:
        console.print(str(error), style='warning')
    finally:
        if trainer.bluetooth_interface:
            await trainer.bluetooth_disconnect()

    return 0


def tools(command, options):
    cube = options.cube

    stack = load_all_solves(
        cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )

    session_stats = StatisticsReporter(
        cube,
        stack,
    )

    if not session_stats.stack:
        console.print(
            f'No saved solves yet for { session_stats.cube_name }.',
            style='warning',
        )
        return 1

    if command == 'list':
        session_stats.listing(options.count, options.sort)

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
                show_cube=options.show_cube,
                show_reconstruction=options.show_reconstruction,
                show_tps_graph=options.show_tps_graph,
                show_time_graph=options.show_time_graph,
                show_recognition_graph=options.show_recognition_graph,
            )

    return 0


def manage(command, options):
    cube = options.cube

    if command == 'edit':
        for solve_id in options.solves:
            manager = SolveManager(cube, options.session, solve_id)
            manager.update(options.flag)

    if command == 'delete':
        manager = SolveManager(cube, options.session, options.solve)
        manager.delete()

    return 0


def main() -> int:
    configure_logging()

    options = get_arguments()
    command = COMMAND_RESOLUTIONS.get(options.command, options.command)

    with suppress(KeyboardInterrupt):
        if command == 'solve':
            return asyncio.run(timer(options), debug=DEBUG)
        if command == 'train':
            return asyncio.run(trainer(options), debug=DEBUG)
        if command == 'import':
            return Importer().import_file(options.source)
        if command == 'serve':
            Server().run_server(options.host, options.port, DEBUG)
            return 0
        if command in {'edit', 'delete'}:
            return manage(command, options)
        return tools(command, options)
