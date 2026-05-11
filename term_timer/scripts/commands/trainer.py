"""Trainer command."""
from argparse import Namespace
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.exceptions import InvalidCaseError
from term_timer.interface.console import console
from term_timer.trainer import Trainer


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
        instance = Trainer(
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

    if options.list_cases:
        instance.list_cases()
        return 0

    if options.bluetooth:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    trainings_done = 0

    try:
        while 42:
            done = await instance.start()

            if done:
                trainings_done += 1

                if options.trainings and trainings_done >= options.trainings:
                    break
            else:
                break
    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
