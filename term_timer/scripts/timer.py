import asyncio
import logging
from random import seed

from term_timer.arguments import get_arguments
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.stats import StatisticsReporter
from term_timer.timer import Timer


async def timer() -> int:  # noqa: PLR0912
    options = get_arguments()

    logging.disable(logging.INFO)

    cube = options.cube
    if options.stats or options.list or options.graph:
        session_stats = StatisticsReporter(cube, load_solves(cube))

        if options.list:
            session_stats.listing(options.list)

        if options.stats:
            session_stats.resume('Global ', show_title=True)

        if options.graph:
            session_stats.graph()

        return 0

    free_play = options.free_play
    if options.seed or options.iterations or options.easy_cross:
        free_play = True

    stack = [] if free_play else load_solves(cube)

    if options.seed:
        seed(options.seed)

    solves_done = 0

    timer = Timer(
        cube_size=cube,
        iterations=options.iterations,
        easy_cross=options.easy_cross,
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

    if not free_play:
        save_solves(cube, timer.stack)

    if len(stack) > 1:
        session_stats = StatisticsReporter(cube, stack)
        session_stats.resume((free_play and 'Session ') or 'Global ')

    return 0


def main() -> int:
    return asyncio.run(timer())
