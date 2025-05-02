import asyncio
import logging
from random import seed

from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import get_arguments
from term_timer.console import console
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.stats import StatisticsReporter
from term_timer.timer import Timer


async def timer() -> int:
    logging.disable(logging.INFO)

    options = get_arguments()
    command = COMMAND_RESOLUTIONS.get(options.command, options.command)

    cube = options.cube

    if command in {'list', 'stats', 'graph', 'cfop', 'detail'}:
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
            session_stats.cfop(options.oll, options.pll)

        if command == 'graph':
            session_stats.graph()

        if command == 'detail':
            for solve_id in options.solves:
                session_stats.detail(solve_id)

        return 0

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
        session_stats.resume((free_play and 'Session ') or 'Global ')

    return 0


def main() -> int:
    return asyncio.run(timer())
