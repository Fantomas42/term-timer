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


def select_ghost(
        reference: Solve,
        history: list[Solve],
        options: Namespace,
) -> Solve:
    """
    Pick the ghost to beat: the fastest analysable solve on the scramble.

    The pool is the scramble's stored attempts plus the reference solve,
    deduplicated by date, so the first race (empty history) beats the
    reference itself. The chosen ghost is analysed with the command's
    method and orientation to align its splits with the live checkpoints.

    Returns:
        The fastest analysable Solve on the scramble.

    """
    candidates: dict[int, Solve] = {}
    for solve in [*history, reference]:
        if solve.analysable:
            candidates[solve.date] = solve

    ghost = min(candidates.values(), key=operator.attrgetter('time'))
    ghost.method_name = options.method
    ghost.orientation = options.orientation

    return ghost


def refresh_ghost(
        instance: Timer,
        reference: Solve,
        history: list[Solve],
        options: Namespace,
) -> None:
    """
    Re-elect the ghost after an attempt.

    The pool is the stored history plus the attempts of the running
    session, so beating the ghost immediately promotes the fresh solve as
    the target of the next race. Free play never writes to the scramble
    file but its attempts still count for the session.

    Args:
        instance: The running timer, holding the current ghost and the
            attempts done in this session.
        reference: The solve whose scramble is being raced.
        history: The attempts stored for that scramble at startup.
        options: Command options carrying the method and orientation.

    """
    if instance.ghost is None:
        return

    instance.ghost = select_ghost(
        reference,
        [*history, *instance.stack_done],
        options,
    )


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


def ghost_summary(cube: int) -> int:
    """
    Browse the ghost library: one row per raced scramble.

    Returns:
        Exit code (0 for success, 1 if no ghost scrambles exist).

    """
    prefix = f'{ cube }x{ cube }x{ cube }-'

    rows: list[tuple[str, int, int]] = []
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

            analysable = [solve for solve in stack if solve.analysable]
            best = min(
                (solve.time for solve in analysable),
                default=0,
            )
            rows.append((str(stack[0].scramble), len(stack), best))

    if not rows:
        console.print(
            '🤔 No ghost scrambles recorded yet.',
            style='warning',
        )
        return 1

    console.print('[title]Ghost Library[/title]')
    for scramble, attempts, best in rows:
        console.print(
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
        return ghost_summary(cube)

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
    ghost_solve = select_ghost(reference, history, options)

    console.print(
        f'[ghost]{ GHOST_EMOJI } Ghost Race - '
        f'Scramble #{ options.solve_id }[/ghost] '
        f'[time]{ format_time(ghost_solve.time) }[/time]',
    )

    stack = [] if options.free_play else history

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

            refresh_ghost(instance, reference, history, options)

            if not done:
                break

        if len(instance.stack) > 1:
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
