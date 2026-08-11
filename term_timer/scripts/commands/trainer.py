"""Trainer command."""
from argparse import Namespace
from random import Random

from term_timer.bluetooth.replay import load_trainer_replay
from term_timer.exceptions import SESSION_ERRORS
from term_timer.exceptions import EmptyCasePoolError
from term_timer.exceptions import ReplayError
from term_timer.interface.console import console
from term_timer.scripts.commands.session import solve_session
from term_timer.stats import TrainerStatistics
from term_timer.trainer import Trainer

# The replay derives its execution from the reference solution of the
# case, and those steps are scrambled without one: nothing to play.
SOLUTIONLESS_STEPS = ('cross', 'll')


def incompatible_options(options: Namespace) -> str:
    """
    Report the combination of options the session cannot honour.

    Returns:
        The reason the session cannot run, empty when it can.

    """
    if options.case_codes and options.filters:
        return '--cases and --filter cannot be used together'

    if options.replay and options.step in SOLUTIONLESS_STEPS:
        return (
            f'--replay cannot drive the { options.step } step, '
            'which is trained without a reference solution'
        )

    return ''


async def trainer(options: Namespace) -> int:  # noqa: PLR0911
    """
    Generate training case.

    Returns:
        Exit code (0 for success).

    """
    incompatible = incompatible_options(options)
    if incompatible:
        console.print('😱', incompatible, style='warning')
        return 1

    rng = Random(options.seed) if options.seed else Random()  # noqa: S311

    try:
        replay = load_trainer_replay(options.replay)
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return 1

    try:
        instance = Trainer(
            step=options.step,
            case_codes=options.case_codes,
            oldest=options.oldest,
            slowest=options.slowest,
            random=options.random,
            filters=options.filters,
            states=options.states,
            new_cases_limit=options.new_cases,
            free_play=options.free_play,
            orientation=options.orientation,
            show_solution=options.show_solution,
            show_cube=options.show_cube,
            metronome=options.metronome,
            rng=rng,
        )
    except EmptyCasePoolError as error:
        if options.list_cases:
            console.print(str(error), style='warning')
            return 0
        console.print('😱', str(error), style='warning')
        return 1
    except SESSION_ERRORS as error:
        console.print('😱', str(error), style='warning')
        return 1

    if options.list_cases:
        instance.list_cases()
        return 0

    if replay is not None:
        instance.bluetooth_replay = replay

    instance.trainer_line()

    return await run_trainings(instance, options)


async def run_trainings(instance: Trainer, options: Namespace) -> int:
    """
    Run the training loop, then report on the session.

    Args:
        instance: The trainer to run.
        options: The parsed command options.

    Returns:
        Exit code (0 for success).

    """
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
