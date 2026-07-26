"""Daily scramble command."""
import operator
from argparse import Namespace
from datetime import date
from datetime import datetime
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.bluetooth.replay import load_scramble_replay
from term_timer.constants import DAILY_DIRECTORY
from term_timer.exceptions import ReplayError
from term_timer.formatter import format_time
from term_timer.in_out import load_all_daily_solves
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import DailySummaryReporter
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


def select_ghost(
        history: list[Solve],
        options: Namespace,
) -> Solve | None:
    """
    Pick the ghost to beat: the day's fastest analysable solve.

    Unlike the ghost command, the first attempt of the day has nothing to
    race: the day only gets a ghost once one of its solves is analysable.
    The chosen ghost is analysed with the command's method and
    orientation to align its splits with the live checkpoints.

    Returns:
        The fastest analysable Solve of the day, or None when there is
        none yet.

    """
    candidates = [solve for solve in history if solve.analysable]
    if not candidates:
        return None

    ghost = min(candidates, key=operator.attrgetter('time'))
    ghost.method_name = options.method
    ghost.orientation = options.orientation

    return ghost


def refresh_ghost(
        instance: Timer,
        history: list[Solve],
        options: Namespace,
) -> None:
    """
    Re-elect the ghost after an attempt.

    The pool is the day's stored solves plus the attempts of the running
    session, so beating the ghost immediately promotes the fresh solve as
    the target of the next race. Free play never writes to the daily file
    but its attempts still count for the session.

    Args:
        instance: The running timer, holding the current ghost and the
            attempts done in this session.
        history: The solves stored for that day at startup.
        options: Command options carrying the method and orientation.

    """
    instance.ghost = select_ghost(
        [*history, *instance.stack_done],
        options,
    )


def daily_header(date_str: str, ghost_solve: Solve | None) -> str:
    """
    Build the session header, carrying the time to beat when raced.

    Returns:
        The header line to print.

    """
    header = f'[routine]📅 Daily Scramble - { date_str }[/routine]'
    if ghost_solve is not None:
        header += f' [time]{ format_time(ghost_solve.time) }[/time]'

    return header


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

    console.print(
        f'[title]Daily summary for { date_str } on '
        f'{ cube }x{ cube }x{ cube }[/title]',
    )

    stats = SolveStatisticsReporter(cube, stack)
    stats.resume()
    stats.graph('Tendency')

    return 0


def daily_summary(cube: int) -> int:
    """
    Show the participation summary across all daily sessions.

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
    summary = DailySummaryReporter(cube, stack)
    summary.resume()
    summary.punchcard()
    summary.days_table()
    return 0


async def daily(options: Namespace) -> int:  # noqa: C901
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

    try:
        replay = load_scramble_replay(
            options.replay,
            scramble_str,
        )
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return 1

    history = load_solves(cube, session, directory=DAILY_DIRECTORY)
    ghost_solve = select_ghost(history, options)

    console.print(daily_header(date_str, ghost_solve))

    stack = [] if options.free_play else history

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
    instance.ghost = ghost_solve

    if replay is not None:
        instance.bluetooth_replay = replay

    if options.bluetooth or replay is not None:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    try:
        while 42:
            done = await instance.start()

            refresh_ghost(instance, history, options)

            if not done:
                break

        if len(instance.stack) > 1:
            console.print(
                f'[title]Daily summary on '
                f'{ cube }x{ cube }x{ cube }[/title]',
            )

            stats = SolveStatisticsReporter(cube, instance.stack)
            stats.resume()
            stats.graph('Tendency')

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
