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
from term_timer.scripts.commands.session import race_header
from term_timer.scripts.commands.session import run_seeded_race
from term_timer.stats import DailySummaryReporter
from term_timer.stats import SolveStatisticsReporter


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

    console.print(
        f'[title]Daily summary for { date_str } on '
        f'{ cube }x{ cube }x{ cube }[/title]',
    )

    stats = SolveStatisticsReporter(cube, stack)
    stats.print_summary()
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
    summary.print_summary()
    summary.punchcard()
    summary.days_table()
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
        return 1

    console.print(
        race_header(
            f'[daily]📅 Daily Scramble - { date_str }[/daily]',
            instance.ghost,
        ),
    )

    return await run_seeded_race(
        instance,
        options,
        f'Daily summary on { cube }x{ cube }x{ cube }',
    )
