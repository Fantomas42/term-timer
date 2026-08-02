"""Trainer command."""
from argparse import Namespace
from random import Random

from term_timer.exceptions import SESSION_ERRORS
from term_timer.interface.console import console
from term_timer.scripts.commands.session import solve_session
from term_timer.stats import TrainerStatistics
from term_timer.trainer import Trainer


async def trainer(options: Namespace) -> int:
    """
    Generate training case.

    Returns:
        Exit code (0 for success).

    """
    if options.case_codes and options.filters:
        console.print(
            '😱 --cases and --filter cannot be used together',
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
            random=options.random,
            filters=options.filters,
            new_cases_limit=options.new_cases,
            free_play=options.free_play,
            orientation=options.orientation,
            show_solution=options.show_solution,
            show_cube=options.show_cube,
            metronome=options.metronome,
            rng=rng,
        )
    except SESSION_ERRORS as error:
        console.print('😱', str(error), style='warning')
        return 1

    if options.list_cases:
        instance.list_cases()
        return 0

    instance.trainer_line()

    async with solve_session(instance, options) as outcome:
        while 42:
            done = await instance.start()

            if done:
                outcome.attempts += 1

                if options.trainings and outcome.attempts >= options.trainings:
                    break
            else:
                break
        if len(instance.session_data) >= 2:
            TrainerStatistics(
                instance.session_data,
                instance.trainings.cases,
            ).print_summary()

    return outcome.code
