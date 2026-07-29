"""Ghost racing command."""
import operator
from argparse import Namespace
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.bluetooth.replay import load_scramble_replay
from term_timer.constants import GHOST_EMOJI
from term_timer.constants import GHOSTS_DIRECTORY
from term_timer.exceptions import ReplayError
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import scramble_to_key
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer


def load_reference(options: Namespace) -> Solve | None:
    """
    Resolve the reference solve from its id within the selected pool.

    The pool is the conjunction of the session options
    (``-c``/``-u``/``-x``/``-d``), mirroring how ``detail`` indexes solves.
    Prints a warning and returns None when the id is missing or out of
    range.

    Returns:
        The reference Solve, or None when it cannot be resolved.

    """
    if options.solve_id <= 0:
        console.print(
            '🤔 Provide the id of a reference solve to race.',
            style='warning',
        )
        return None

    stack = load_all_solves(
        options.cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )

    try:
        reference: Solve = stack[options.solve_id - 1]
    except IndexError:
        console.print(
            f'Invalid solve #{ options.solve_id }',
            style='warning',
        )
        return None

    reference.method_name = options.method
    reference.orientation = options.orientation

    return reference


def build_race_stack(
        reference: Solve,
        history: list[Solve],
        key: str,
) -> list[Solve]:
    """
    Seed the scramble history with the reference solve.

    The reference is an attempt on that scramble like any other, so it
    joins the stack as attempt #1: records, live series and projections
    then have a real baseline from the very first race, and the file
    written back to ``ghosts/`` becomes self-contained. Deduplication by
    date keeps it single once a race has stored it, and re-seeds it if
    the file is ever deleted.

    Args:
        reference: The solve whose scramble is being raced.
        history: The attempts stored for that scramble.
        key: The scramble key naming the ghost file.

    Returns:
        The attempts on the scramble, oldest first, renumbered.

    """
    uniques: dict[int, Solve] = {reference.date: reference}
    for solve in history:
        uniques[solve.date] = solve

    stack = sorted(uniques.values(), key=operator.attrgetter('date'))

    for index, solve in enumerate(stack):
        solve.session = key
        solve.solve_id = index + 1

    return stack


def select_ghost(
        stack: list[Solve],
        options: Namespace,
) -> Solve:
    """
    Pick the ghost to beat: the fastest solve on the scramble.

    The pool is the race stack, which already carries the reference solve
    as its first attempt, so the very first race beats the reference
    itself and the stack is never without a candidate. Every attempt is
    eligible, timed on the cube or on the keyboard, so a race run
    without a connected cube still moves its target; a keyboard ghost
    simply carries no reconstruction, hence no checkpoint splits. Times
    are compared on ``final_time``: a DNF has none, and a +2 races with
    the two seconds it costs. The chosen ghost is analysed with the
    command's method and orientation to align its splits with the live
    checkpoints.

    Returns:
        The fastest non-DNF Solve on the scramble.

    """
    candidates = [solve for solve in stack if solve.final_time]

    ghost = min(candidates, key=operator.attrgetter('final_time'))
    ghost.method_name = options.method
    ghost.orientation = options.orientation

    return ghost


def refresh_ghost(
        instance: Timer,
        options: Namespace,
) -> None:
    """
    Re-elect the ghost after an attempt.

    The pool is the timer stack, which holds the seeded history plus the
    attempts of the running session, so beating the ghost immediately
    promotes the fresh solve as the target of the next race. Free play
    never writes to the scramble file but its attempts still count for
    the session.

    Args:
        instance: The running timer, holding the current ghost and the
            attempts raced so far.
        options: Command options carrying the method and orientation.

    """
    if instance.ghost is None:
        return

    instance.ghost = select_ghost(instance.stack, options)


def ghost_review(options: Namespace) -> int:
    """
    Show stats and graph for the reference solve's scramble file.

    Returns:
        Exit code (0 for success, 1 if the scramble has no attempts).

    """
    reference = load_reference(options)
    if reference is None:
        return 1

    key = scramble_to_key(str(reference.scramble))
    stack = load_solves(options.cube, key, directory=GHOSTS_DIRECTORY)
    if not stack:
        console.print(
            '🤔 No ghost attempts recorded yet for this scramble.',
            style='warning',
        )
        return 1

    console.print(
        f'[title]Summary on Ghost #{ options.solve_id }[/title]',
    )

    round_stats = SolveStatisticsReporter(options.cube, stack)
    round_stats.print_summary()
    round_stats.graph('Tendency')

    return 0


def reference_ids(options: Namespace) -> dict[int, int]:
    """
    Index the solve pool by date to name a ghost by its reference id.

    A ghost file opens on the solve that seeded it, so its identity is
    that solve's id: the same id the race takes as argument. The pool is
    the one the session options select, exactly as when racing.

    Returns:
        Solve date mapped to its 1-based id in the selected pool.

    """
    stack = load_all_solves(
        options.cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )

    return {solve.date: index + 1 for index, solve in enumerate(stack)}


def ghost_summary(options: Namespace) -> int:
    """
    Browse the ghost library: one row per raced scramble.

    Each row is prefixed by the id of the solve that seeded the ghost,
    ready to be handed back to ``term-timer ghost <id>``. Files seeded
    before the reference was stored, or whose reference falls outside
    the selected pool, show no id.

    The time is the best official time on the scramble, elected exactly
    as the ghost is, so the row announces the time the race will ask you
    to beat. A scramble whose attempts are all DNF has no such time and
    reads DNF.

    Returns:
        Exit code (0 for success, 1 if no ghost scrambles exist).

    """
    cube = options.cube
    prefix = f'{ cube }x{ cube }x{ cube }-'

    rows: list[tuple[int, str, int, int]] = []
    if GHOSTS_DIRECTORY.exists():
        for source in sorted(GHOSTS_DIRECTORY.iterdir()):
            if (
                    not source.is_file()
                    or not source.name.startswith(prefix)
                    or source.name.endswith('~')
            ):
                continue

            key = source.name.split(prefix, 1)[1].replace('.json', '')
            stack = load_solves(cube, key, directory=GHOSTS_DIRECTORY)
            if not stack:
                continue

            best = min(
                (solve.final_time for solve in stack if solve.final_time),
                default=0,
            )
            rows.append(
                (
                    stack[0].date,
                    str(stack[0].scramble),
                    len(stack),
                    best,
                ),
            )

    if not rows:
        console.print(
            '🤔 No ghost scrambles recorded yet.',
            style='warning',
        )
        return 1

    ids = reference_ids(options)

    console.print('[title]Ghost Library[/title]')
    for date, scramble, attempts, best in rows:
        solve_id = ids.get(date, 0)
        label = f'#{ solve_id }' if solve_id else '—'
        console.print(
            f'[round]{ label:>5}[/round] '
            f'[time]{ format_time(best) }[/time] '
            f'[stats]{ attempts:>3} attempts[/stats] '
            f'[moves]{ scramble }[/moves]',
        )
    return 0


async def ghost(options: Namespace) -> int:  # noqa: C901, PLR0912
    """
    Race a live solve against a recorded ghost on the same scramble.

    Returns:
        Exit code (0 for success, 1 on resolution errors).

    """
    cube = options.cube

    if options.summary:
        return ghost_summary(options)

    if options.review:
        return ghost_review(options)

    reference = load_reference(options)
    if reference is None:
        return 1

    if not reference.analysable:
        console.print(
            f'🤔 Solve #{ options.solve_id } has no reconstruction to race '
            '(DNF or not analysable).',
            style='warning',
        )
        return 1

    scramble_str = str(reference.scramble)
    key = scramble_to_key(scramble_str)

    try:
        replay = load_scramble_replay(
            options.replay,
            scramble_str,
        )
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return 1

    history = load_solves(cube, key, directory=GHOSTS_DIRECTORY)
    stack = build_race_stack(reference, history, key)
    ghost_solve = select_ghost(stack, options)

    console.print(
        f'[ghost]{ GHOST_EMOJI } Ghost Race - '
        f'Scramble #{ options.solve_id }[/ghost] '
        f'[time]{ format_time(ghost_solve.final_time) }[/time]',
    )

    instance = Timer(
        cube_size=cube,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble_str,
        scrambles=[],
        session=key,
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
        rng=Random(),  # noqa: S311
    )
    instance.save_directory = GHOSTS_DIRECTORY
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

            refresh_ghost(instance, options)

            if not done:
                break

        if instance.stack_done:
            console.print(
                f'[title]Summary on Ghost #{ options.solve_id }[/title]',
            )

            stats = SolveStatisticsReporter(cube, instance.stack)
            stats.print_summary()
            stats.graph('Tendency')

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
