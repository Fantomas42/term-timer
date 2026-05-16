"""Daily scramble command."""
from argparse import Namespace
from datetime import date
from datetime import datetime
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.constants import DAILY_DIRECTORY
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.scrambler import scrambler
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer


def _parse_date(raw: str) -> date:
    """
    Parse a YYYY-MM-DD string into a date, defaulting to today.

    Returns:
        Parsed date or today's date.

    """
    if raw:
        return datetime.strptime(raw, '%Y-%m-%d').date()  # noqa: DTZ007
    return date.today()  # noqa: DTZ011


async def daily(options: Namespace) -> int:
    """
    Run the daily scramble session.

    Returns:
        Exit code (0 for success).

    """
    cube = options.cube
    daily_date = _parse_date(options.date)
    date_str = daily_date.strftime('%Y-%m-%d')
    session = date_str

    rng = Random(date_str)  # noqa: S311
    daily_scramble, _ = scrambler(cube, 0, rng=rng)
    scramble_str = str(daily_scramble)

    console.print(
        f'[scramble]Daily Scramble — { date_str }[/scramble]',
        style='bold',
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

    if options.bluetooth:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    solves_done = 0

    try:
        while 42:
            done = await instance.start()

            if done:
                solves_done += 1
            else:
                break

        if not options.free_play and instance.stack_done:
            save_solves(
                cube,
                session,
                instance.stack,
                directory=DAILY_DIRECTORY,
            )

        if len(instance.stack_done) > 1:
            round_stats = SolveStatisticsReporter(cube, instance.stack_done)
            round_stats.resume(f'Daily { date_str } ', 'round')

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
