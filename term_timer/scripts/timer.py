import asyncio
from contextlib import suppress
from random import seed

from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import get_arguments
from term_timer.config import DEBUG
from term_timer.console import console
from term_timer.exporters import Exporter
from term_timer.importers import Importer
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.logger import configure_logging
from term_timer.stats import StatisticsReporter
from term_timer.timer import Timer


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
        session_stats.resume('Session ')

    return 0


def tools(command, options):
    cube = options.cube

    session_stats = StatisticsReporter(
        cube,
        load_all_solves(
            cube,
            options.include_sessions,
            options.exclude_sessions,
            options.devices,
        ),
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

    if command == 'cfop':
        session_stats.cfop(
            options.oll, options.pll,
            options.sort, options.order,
        )

    if command == 'graph':
        session_stats.graph()

    if command == 'detail':
        for solve_id in options.solves:
            session_stats.detail(solve_id, options.method)

    if command == 'export':
        Exporter().export_html(session_stats)

    return 0


def main() -> int:
    configure_logging()

    options = get_arguments()
    command = COMMAND_RESOLUTIONS.get(options.command, options.command)

    with suppress(KeyboardInterrupt):
        if command == 'solve':
            return asyncio.run(timer(options), debug=DEBUG)
        if command == 'import':
            Importer().import_file(options.source)
            return 0
        tools(command, options)
        return 0
