"""Driller command."""
import asyncio
import time
from argparse import Namespace

from cubing_algs.exceptions import InvalidMoveError

from term_timer.driller import Driller
from term_timer.exceptions import InvalidAlgorithmError
from term_timer.interface.console import console
from term_timer.stats import DrillStatistics


async def driller(options: Namespace) -> int:  # noqa: C901, PLR0912
    """
    Run algorithm drilling session.

    Returns:
        Exit code (0 for success).

    """
    try:
        instance = Driller(
            algorithm=options.algorithm,
            times=options.times,
            duration=options.duration,
            orientation=options.orientation,
            countdown=options.countdown,
            metronome=options.metronome,
        )
    except InvalidAlgorithmError as error:
        console.print('😱', str(error), style='warning')
        return 1

    if options.bluetooth:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    drills_done = 0
    session_start = time.monotonic()

    try:
        while 42:
            if options.duration:
                elapsed = time.monotonic() - session_start
                remaining = options.duration - elapsed
                if remaining <= 0:
                    break
                try:
                    done = await asyncio.wait_for(
                        instance.start(), timeout=remaining,
                    )
                except TimeoutError:
                    break
            else:
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
                qtm=instance.algorithm.metrics.qtm,
            ).print_summary()

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
        return 1
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
