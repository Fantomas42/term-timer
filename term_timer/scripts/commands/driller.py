"""Driller command."""
from argparse import Namespace

from cubing_algs.exceptions import InvalidMoveError

from term_timer.driller import Driller
from term_timer.interface.console import console
from term_timer.stats import DrillStatistics


async def driller(options: Namespace) -> int:
    """
    Run algorithm drilling session.

    Returns:
        Exit code (0 for success).

    """
    instance = Driller(
        algorithm=options.algorithm,
        times=options.times,
        orientation=options.orientation,
        countdown=options.countdown,
        metronome=options.metronome,
    )

    if options.bluetooth:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    drills_done = 0

    try:
        while 42:
            done = await instance.start()

            if done:
                drills_done += 1

                if options.times and drills_done >= options.times:
                    break
            else:
                break

        if len(instance.rep_times) >= 2:
            DrillStatistics(
                instance.rep_times,
                instance.rep_tps,
                instance.rep_fluencies,
            ).resume()

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
