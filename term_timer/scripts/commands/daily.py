"""Daily scramble command."""
from argparse import Namespace
from datetime import date
from datetime import datetime
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.constants import DAILY_DIRECTORY
from term_timer.in_out import load_all_daily_solves
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.scrambler import scrambler
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer


def parse_date(raw: str) -> date:
    """
    Parse a YYYY-MM-DD string into a date, defaulting to today.

    Returns:
        Parsed date or today's date.

    """
    if raw:
        return datetime.strptime(raw, '%Y-%m-%d').date()  # noqa: DTZ007
    return date.today()  # noqa: DTZ011


def daily_review(cube: int, date_str: str) -> int:
    """
    Show stats and graph for a single daily session.

    Returns:
        Exit code (0 for success, 1 if no solves found).

    """
    stack = load_solves(cube, date_str, directory=DAILY_DIRECTORY)
    if not stack:
        console.print(
            f'🤔 No solves recorded for daily { date_str }.',
            style='warning',
        )
        return 1
    round_stats = SolveStatisticsReporter(cube, stack)
    round_stats.resume(f'Daily { date_str } ', 'round')
    round_stats.graph()
    return 0


def daily_summary(cube: int) -> int:
    """
    Show stats and graph across all daily sessions.

    Returns:
        Exit code (0 for success, 1 if no solves found).

    """
    stack = load_all_daily_solves(cube)
    if not stack:
        console.print(
            '🤔 No daily solves recorded yet.',
            style='warning',
        )
        return 1
    all_stats = SolveStatisticsReporter(cube, stack)
    all_stats.resume('Daily - All sessions ', show_title=True)
    all_stats.graph()
    return 0


async def daily(options: Namespace) -> int:
    """
    Run the daily scramble session.

    Returns:
        Exit code (0 for success).

    """
    cube = options.cube
    daily_date = parse_date(options.date)
    date_str = daily_date.strftime('%Y-%m-%d')

    if options.summary:
        return daily_summary(cube)

    if options.review:
        return daily_review(cube, date_str)

    session = date_str
    rng = Random(date_str)  # noqa: S311
    daily_scramble, _ = scrambler(cube, 0, rng=rng)
    scramble_str = str(daily_scramble)

    console.print(
        f'📅 Daily Scramble - { date_str }',
        style='routine',
    )

    stack = [] if options.free_play else load_solves(
        cube,
        session,
        directory=DAILY_DIRECTORY,
    )

    instance = Timer(
        cube_size=cube,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble_str,
        scrambles=[],
        session=session,
        free_play=options.free_play,
        show_highlights=options.show_highlights,
        show_doctor=options.show_doctor,
        show_cube=options.show_cube,
        show_reconstruction=options.show_reconstruction,
        show_tps_graph=options.show_tps_graph,
        show_time_graph=options.show_time_graph,
        show_fluency_graph=options.show_fluency_graph,
        show_recognition_graph=options.show_recognition_graph,
        show_steps=options.show_steps,
        method=options.method,
        orientation=options.orientation,
        countdown=options.countdown,
        metronome=options.metronome,
        stack=stack,
        rng=rng,
    )
    instance.save_directory = DAILY_DIRECTORY

    if options.bluetooth:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    try:
        while 42:
            done = await instance.start()

            if not done:
                break

        if len(instance.stack_done) > 1:
            round_stats = SolveStatisticsReporter(cube, instance.stack_done)
            round_stats.resume(f'Daily { date_str } ', 'round')
            round_stats.graph()

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
