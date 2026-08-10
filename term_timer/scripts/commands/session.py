"""Shared plumbing of the solving commands."""
import time
from argparse import Namespace
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from random import Random

from term_timer.aggregator import SolvesDoctorAggregator
from term_timer.bluetooth.replay import load_scramble_replay
from term_timer.exceptions import SESSION_ERRORS
from term_timer.exceptions import ReplayError
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.interface.console import console
from term_timer.interface.doctor import DoctorReporter
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer
from term_timer.wakelock import keep_awake


@dataclass
class SessionOutcome:
    """The exit code the session ends on, and what it produced."""

    code: int = 0
    attempts: int = 0


@asynccontextmanager
async def solve_session(
        instance: SolveInterface,
        options: Namespace,
) -> AsyncIterator[SessionOutcome]:
    """
    Hold the Bluetooth connection around the loop of a solving command.

    The cube is connected on entry when the command asks for it or
    replays a solve file, and disconnected on exit whatever happens.
    An unusable algorithm, case or cube state ends the session on the
    exit code carried by the yielded outcome, every other exception
    propagating untouched.

    Commands that never accept --replay leave bluetooth_replay unset,
    so the connection there falls back on the --bluetooth flag alone.

    Solving on a smart cube produces no keyboard nor mouse event, so the
    session also holds a wake lock: without it the screen blanks and the
    machine suspends in the middle of a session. A system offering no
    usable inhibitor is not an error, the session simply runs without.

    The time spent in the session is measured from the connected cube on,
    the pairing of a cube being a wait, not practice, and printed on the
    way out as long as the command counted an attempt: a session left
    right away has no duration worth reading.

    Yields:
        The outcome carrying the exit code the command returns and the
        count of the attempts it recorded.

    """
    if options.bluetooth or instance.bluetooth_replay is not None:
        await instance.bluetooth_connect(
            options.bluetooth,
            use_gyroscope=options.use_gyroscope,
        )

    outcome = SessionOutcome()
    started_at = time.monotonic_ns()

    try:
        with keep_awake():
            yield outcome
    except SESSION_ERRORS as error:
        console.print('😱', str(error), style='warning')
        outcome.code = 1
    finally:
        if outcome.attempts:
            elapsed_ns = time.monotonic_ns() - started_at
            console.print(
                '⏳ [title]Session duration[/title] '
                f'[time]{ format_time(elapsed_ns, allow_dnf=False) }[/time]',
            )

        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()


def race_header(title: str, ghost_solve: Solve | None) -> str:
    """
    Build the session header, carrying the time to beat when there is one.

    Args:
        title: The styled title naming the session.
        ghost_solve: The elected ghost, None when nothing is raced yet.

    Returns:
        The header line to print.

    """
    if ghost_solve is None:
        return title

    return f'{ title } [time]{ format_time(ghost_solve.final_time) }[/time]'


def print_scramble_doctor(options: Namespace, stack: list[Solve]) -> None:
    """
    Print the aggregated doctor report of a raced scramble.

    Every attempt of the stack solves the same scramble, so the very
    same cross and the very same pairs get diagnosed over and over: a
    finding recurring at a location names a weakness on that case, where
    a window of varied scrambles would only average one out. It is
    printed from the first attempt on, a lone diagnostic staying worth
    reading.

    Locations remain indexed by step position, not by case, so two
    attempts solving the pairs in a different order do not line their
    F2L slots up. The scramble being fixed makes it far more coherent
    than a regular window, not an identity.

    No trend accompanies it: a fixed scramble has no preceding window of
    its own to compare against.

    Args:
        options: The parsed command options.
        stack: The attempts recorded on the scramble.

    """
    if not options.show_doctor:
        return

    analysable = [solve for solve in stack if solve.analysable]
    if not analysable:
        return

    aggregator = SolvesDoctorAggregator(options.method, analysable)
    total = aggregator.results['total']
    if not total:
        return

    plural = 's' if total > 1 else ''
    reporter = DoctorReporter(aggregator.results)
    console.print(
        reporter.report(
            subject=f'{ total } attempt{ plural } on this scramble',
        ),
    )


def print_scramble_review(
        options: Namespace,
        stack: list[Solve],
        title: str,
) -> int:
    """
    Print the review of the attempts recorded on a fixed scramble.

    The listing sits between the summary and the tendency graph: the
    aggregate answers how the round went, the listing which attempts
    say so, and the graph draws them. Its ids address the attempts in
    ``--detail``.

    Args:
        options: The parsed command options.
        stack: The attempts recorded on the scramble.
        title: The heading naming the scramble reviewed.

    Returns:
        Exit code (0 for success).

    """
    console.print(f'[title]{ title }[/title]')

    stats = SolveStatisticsReporter(options.cube, stack)
    stats.print_summary()
    stats.attempts_listing()
    stats.graph('Tendency')

    print_scramble_doctor(options, stack)

    return 0


def print_scramble_details(
        options: Namespace,
        stack: list[Solve],
) -> int:
    """
    Print the detail of the attempts named by ``--detail``.

    The ids are the ones the review listing prints, a 1-based position
    in the scramble file. An id naming no attempt is reported and the
    remaining ones are still printed, an unusable id in a list being no
    reason to withhold the details that resolve.

    Args:
        options: The parsed command options.
        stack: The attempts recorded on the scramble.

    Returns:
        Exit code (0 for success, 1 if an id names no attempt).

    """
    stats = SolveStatisticsReporter(options.cube, stack)

    code = 0
    for solve_id in options.detail:
        if solve_id < 1 or solve_id > len(stack):
            console.print(
                f'Invalid solve #{ solve_id }',
                style='warning',
            )
            code = 1
            continue

        stats.detail(
            solve_id,
            options.method,
            options.orientation,
            disable_rotations=False,
            show_highlights=options.show_highlights,
            show_doctor=options.show_doctor,
            show_cube=options.show_cube,
            show_reconstruction=options.show_reconstruction,
            show_tps_graph=options.show_tps_graph,
            show_time_graph=options.show_time_graph,
            show_fluency_graph=options.show_fluency_graph,
            show_recognition_graph=options.show_recognition_graph,
        )

    return code


def build_race_timer(  # noqa: PLR0913
        options: Namespace, *,
        session: str,
        scramble: str,
        stack: list[Solve],
        rng: Random,
        save_directory: Path,
) -> Timer | None:
    """
    Build the timer of a session run on a single imposed scramble.

    The scramble being given, the whole scramble generation group is
    fixed: no iteration, no cross constraint, no scramble list. What
    remains varies from one command to the next, hence the keywords.

    The save directory, the replay payload and the ghost stay out of the
    Timer signature and are posted here, on the command side.

    Args:
        options: The parsed command options.
        session: The session name the solves are saved under.
        scramble: The scramble every attempt of the session solves.
        stack: The solves seeding the session.
        rng: The random source, seeded when the scramble is.
        save_directory: Where the session writes its solves.

    Returns:
        The ready timer, or None when the replay file is unusable, its
        error being printed.

    """
    try:
        replay = load_scramble_replay(options.replay, scramble)
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return None

    instance = Timer(
        cube_size=options.cube,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble,
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
    instance.save_directory = save_directory

    if replay is not None:
        instance.bluetooth_replay = replay

    instance.elect_ghost()

    return instance


async def run_seeded_race(
        instance: Timer,
        options: Namespace,
        title: str,
) -> int:
    """
    Run the race loop of a session, then report on the scramble.

    The ghost is re-elected after every attempt, so beating it moves the
    target for the next one. The closing summary covers the whole stack,
    seeding solves included, and is skipped while the session holds a
    single attempt: there is nothing to compare yet.

    Args:
        instance: The timer to run.
        options: The parsed command options.
        title: The title of the closing summary.

    Returns:
        Exit code (0 for success, 1 on an invalid move).

    """
    async with solve_session(instance, options) as outcome:
        while 42:
            done = await instance.start()

            instance.elect_ghost()

            if not done:
                break

            outcome.attempts += 1

        if len(instance.stack) > 1:
            console.print(f'[title]{ title }[/title]')

            stats = SolveStatisticsReporter(
                instance.cube_size, instance.stack,
            )
            stats.print_summary()
            stats.graph('Tendency')

    return outcome.code
