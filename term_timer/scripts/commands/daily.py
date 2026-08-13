"""Daily scramble command."""
from argparse import Namespace
from datetime import date
from datetime import datetime
from random import Random

from term_timer.constants import DAILY_DIRECTORY
from term_timer.in_out import load_all_daily_solves
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.scrambler import scrambler
from term_timer.scripts.commands.session import build_race_timer
from term_timer.scripts.commands.session import print_scramble_details
from term_timer.scripts.commands.session import print_scramble_review
from term_timer.scripts.commands.session import race_header
from term_timer.scripts.commands.session import run_seeded_race
from term_timer.solve import Solve
from term_timer.stats import DailySummaryReporter
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


def daily_stack(options: Namespace, date_str: str) -> list[Solve] | None:
    """
    Load the attempts recorded on a daily scramble.

    Prints a warning and returns None when the day holds none.

    Returns:
        The attempts of the day, or None.

    """
    stack = load_solves(options.cube, date_str, directory=DAILY_DIRECTORY)
    if not stack:
        console.print(
            f'🤔 No solves recorded for daily { date_str }.',
            style='warning',
        )
        return None

    return stack


def daily_review(options: Namespace, date_str: str) -> int:
    """
    Show stats, listing, graph and diagnostics for a daily session.

    Every attempt of the day shares the daily scramble, so the review
    closes on the doctor report of that scramble.

    Returns:
        Exit code (0 for success, 1 if no solves found).

    """
    stack = daily_stack(options, date_str)
    if stack is None:
        return 1

    cube = options.cube

    return print_scramble_review(
        options,
        stack,
        f'Daily summary for { date_str } on { cube }x{ cube }x{ cube }',
    )


def daily_detail(options: Namespace, date_str: str) -> int:
    """
    Show the detail of the daily attempts named by --detail.

    Returns:
        Exit code (0 for success, 1 if no solves found or an id names
        no attempt).

    """
    stack = daily_stack(options, date_str)
    if stack is None:
        return 1

    return print_scramble_details(options, stack)


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
    summary.print_summary()
    console.print()
    summary.punchcard()
    summary.days_table()
    return 0


def daily_report(options: Namespace, date_str: str) -> int | None:
    """
    Answer the reading modes of the command, before any scramble.

    The participation summary comes first, then the detail of an
    attempt, then the review it is read from: naming an attempt implies
    the review it belongs to.

    Returns:
        The exit code of the mode asked for, or None when none is and
        the command has a scramble to run.

    """
    if options.summary:
        return daily_summary(options.cube)

    if options.detail:
        return daily_detail(options, date_str)

    if options.review:
        return daily_review(options, date_str)

    return None


def build_daily_timer(options: Namespace, date_str: str) -> Timer | None:
    """
    Build the timer racing the daily scramble of a date, header printed.

    The date seeds the scramble, so the same day always yields the same
    one, and the attempts already made on it seed the stack. The command
    and a routine step both race from here, the date being the only
    thing they resolve differently.

    Args:
        options: The parsed command options.
        date_str: The day being raced, as ``YYYY-MM-DD``.

    Returns:
        The ready timer, or None when it cannot be built, its error
        being printed.

    """
    cube = options.cube

    rng = Random(date_str)  # noqa: S311
    daily_scramble, _ = scrambler(cube, 0, rng=rng)

    instance = build_race_timer(
        options,
        session=date_str,
        scramble=str(daily_scramble),
        stack=load_solves(cube, date_str, directory=DAILY_DIRECTORY),
        rng=rng,
        save_directory=DAILY_DIRECTORY,
    )
    if instance is None:
        return None

    console.print(
        race_header(
            f'[daily]📅 Daily Scramble - { date_str }[/daily]',
            instance.ghost,
        ),
    )

    return instance


async def daily(options: Namespace) -> int:
    """
    Run the daily scramble session.

    Returns:
        Exit code (0 for success).

    """
    cube = options.cube
    daily_date = parse_date(options.date)
    date_str = daily_date.strftime('%Y-%m-%d')

    report = daily_report(options, date_str)
    if report is not None:
        return report

    instance = build_daily_timer(options, date_str)
    if instance is None:
        return 1

    return await run_seeded_race(
        instance,
        options,
        f'Daily summary on { cube }x{ cube }x{ cube }',
    )
