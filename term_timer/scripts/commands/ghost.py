"""Ghost racing command."""
import operator
from argparse import Namespace
from random import Random
from typing import Final
from typing import NamedTuple

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

KEY_MINIMUM: Final[int] = 4
KEY_SHORT: Final[int] = 8


class GhostReference(NamedTuple):
    """
    The scramble a race targets, and how to address it.

    Attributes:
        solve: The solve seeding the race, freshest copy available.
        key: The scramble key naming the ghost file.
        label: How that scramble is named on screen.

    """

    solve: Solve
    key: str
    label: str


def ghost_keys(cube: int) -> list[str]:
    """
    List the scramble keys the ghost library holds for a cube size.

    Returns:
        The keys, in whatever order the filesystem yields them.

    """
    if not GHOSTS_DIRECTORY.exists():
        return []

    prefix = f'{ cube }x{ cube }x{ cube }-'

    return [
        source.name.split(prefix, 1)[1].replace('.json', '')
        for source in GHOSTS_DIRECTORY.iterdir()
        if (
                source.is_file()
                and source.name.startswith(prefix)
                and not source.name.endswith('~')
        )
    ]


def resolve_key(cube: int, prefix: str) -> str | None:
    """
    Match a scramble key prefix against the ghost library.

    A key is the permanent address of a raced scramble: unlike the
    reference id, a position in a filtered pool, it survives a deletion,
    an import or a change of session options. Any unambiguous prefix of
    at least four characters names it, the way a short hash names a
    commit.

    Returns:
        The matching key, or None when the prefix is too short, unknown
        or ambiguous.

    """
    if len(prefix) < KEY_MINIMUM:
        console.print(
            f'A scramble key needs at least { KEY_MINIMUM } characters',
            style='warning',
        )
        return None

    matches = sorted(
        key
        for key in ghost_keys(cube)
        if key.startswith(prefix)
    )

    if not matches:
        console.print(
            f'Invalid scramble key { prefix }',
            style='warning',
        )
        return None

    if len(matches) > 1:
        console.print(
            f'Ambiguous scramble key { prefix }: '
            f'{ ", ".join(matches) }',
            style='warning',
        )
        return None

    return matches[0]


def reference_from_id(
        pool: list[Solve],
        solve_id: int,
) -> GhostReference | None:
    """
    Resolve the reference from its 1-based position in the pool.

    Returns:
        The resolved reference, or None when the id falls outside the
        pool.

    """
    if solve_id < 1 or solve_id > len(pool):
        console.print(
            f'Invalid solve #{ solve_id }',
            style='warning',
        )
        return None

    reference = pool[solve_id - 1]

    return GhostReference(
        reference,
        scramble_to_key(str(reference.scramble), reference.cube_size),
        f'#{ solve_id }',
    )


def reference_from_key(
        pool: list[Solve],
        cube: int,
        prefix: str,
) -> GhostReference | None:
    """
    Resolve the reference from the key of the scramble it seeded.

    A ghost file carries its own seed as attempt #1, so a scramble stays
    raceable by key once its reference has left the pool — deleted, or
    filtered out by the session options — where its id no longer names
    anything. The pool copy still wins when it is there, so an edit made
    with ``term-timer edit`` keeps reaching the race.

    Returns:
        The resolved reference, or None when the key matches no stored
        scramble.

    """
    key = resolve_key(cube, prefix)
    if key is None:
        return None

    history = load_solves(cube, key, directory=GHOSTS_DIRECTORY)
    if not history:
        console.print(
            f'Empty scramble key { prefix }',
            style='warning',
        )
        return None

    seed = history[0]
    solve_id = reference_ids(pool).get(seed.date, 0)

    return GhostReference(
        pool[solve_id - 1] if solve_id else seed,
        key,
        f'#{ solve_id }' if solve_id else key[:KEY_SHORT],
    )


def load_reference(options: Namespace) -> GhostReference | None:
    """
    Resolve the scramble to race, by reference id or by scramble key.

    A decimal argument is a 1-based id in the pool the session options
    select (``-c``/``-u``/``-x``/``-d``), mirroring how ``detail``
    indexes solves; anything else is a prefix of the scramble key
    ``--summary`` prints. The id is the handy shortcut, the key the
    permanent address.

    Prints a warning and returns None when the argument resolves to
    nothing.

    Returns:
        The resolved reference, or None.

    """
    if not options.reference:
        console.print(
            '🤔 Provide the id or the key of a reference solve to race.',
            style='warning',
        )
        return None

    pool = load_all_solves(
        options.cube,
        options.include_sessions,
        options.exclude_sessions,
        options.devices,
    )

    if options.reference.isdigit():
        resolved = reference_from_id(pool, int(options.reference))
    else:
        resolved = reference_from_key(pool, options.cube, options.reference)

    if resolved is None:
        return None

    resolved.solve.method_name = options.method
    resolved.solve.orientation = options.orientation

    return resolved


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

    The stored copy is only a cache: the reference loaded from its own
    session wins the deduplication, so a flag corrected with
    ``term-timer edit`` reaches the race — it can move the time to beat,
    or take the reference out of the pool altogether — and the next save
    writes the fresh copy back.

    Args:
        reference: The solve whose scramble is being raced.
        history: The attempts stored for that scramble.
        key: The scramble key naming the ghost file.

    Returns:
        The attempts on the scramble, oldest first, renumbered.

    """
    uniques: dict[int, Solve] = {
        solve.date: solve for solve in history
    }
    uniques[reference.date] = reference

    stack = sorted(uniques.values(), key=operator.attrgetter('date'))

    for index, solve in enumerate(stack):
        solve.session = key
        solve.solve_id = index + 1

    return stack


def select_ghost(
        stack: list[Solve],
        options: Namespace,
) -> Solve | None:
    """
    Pick the ghost to beat: the fastest solve on the scramble.

    The pool is the race stack, which already carries the reference solve
    as its first attempt, so the very first race beats the reference
    itself and the stack normally has a candidate from the start — the
    empty pool is guarded all the same, so a stack that would hold only
    DNFs races without a ghost instead of raising mid-session. Every
    attempt is eligible, timed on the cube or on the keyboard, so a race
    run without a connected cube still moves its target; a keyboard ghost
    simply carries no reconstruction, hence no checkpoint splits. Times
    are compared on ``final_time``: a DNF has none, and a +2 races with
    the two seconds it costs. The chosen ghost is analysed with the
    command's method and orientation to align its splits with the live
    checkpoints.

    Returns:
        The fastest non-DNF Solve on the scramble, or None when every
        attempt is a DNF.

    """
    candidates = [solve for solve in stack if solve.final_time]
    if not candidates:
        return None

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
    instance.ghost = select_ghost(instance.stack, options)


def ghost_header(label: str, ghost_solve: Solve | None) -> str:
    """
    Build the race header, carrying the time to beat when there is one.

    Returns:
        The header line to print.

    """
    header = (
        f'[ghost]{ GHOST_EMOJI } Ghost Race - '
        f'Scramble { label }[/ghost]'
    )
    if ghost_solve is not None:
        header += f' [time]{ format_time(ghost_solve.final_time) }[/time]'

    return header


def ghost_review(options: Namespace) -> int:
    """
    Show stats and graph for the reference solve's scramble file.

    Returns:
        Exit code (0 for success, 1 if the scramble has no attempts).

    """
    reference = load_reference(options)
    if reference is None:
        return 1

    stack = load_solves(
        options.cube, reference.key, directory=GHOSTS_DIRECTORY,
    )
    if not stack:
        console.print(
            '🤔 No ghost attempts recorded yet for this scramble.',
            style='warning',
        )
        return 1

    console.print(
        f'[title]Summary on Ghost { reference.label }[/title]',
    )

    round_stats = SolveStatisticsReporter(options.cube, stack)
    round_stats.print_summary()
    round_stats.graph('Tendency')

    return 0


def reference_ids(pool: list[Solve]) -> dict[int, int]:
    """
    Index a solve pool by date to name a ghost by its reference id.

    A ghost file opens on the solve that seeded it, so it answers to
    that solve's id: the same id the race takes as argument.

    Returns:
        Solve date mapped to its 1-based id in the pool.

    """
    return {solve.date: index + 1 for index, solve in enumerate(pool)}


def ghost_summary(options: Namespace) -> int:
    """
    Browse the ghost library: one row per raced scramble.

    Each row carries the two ways of addressing the scramble: the id of
    the solve that seeded it, a handy shortcut that a deletion or a
    change of session options can shift, and its scramble key, which
    never moves. Both are handed back to ``term-timer ghost <ref>``.
    Files seeded before the reference was stored, or whose reference
    falls outside the selected pool, show no id and answer to their key
    alone.

    The time is the best official time on the scramble, elected exactly
    as the ghost is, so the row announces the time the race will ask you
    to beat. A scramble whose attempts are all DNF has no such time and
    reads DNF.

    Rows are ordered by that time, fastest first — the file names being
    scramble digests, their own order carries no meaning.

    Returns:
        Exit code (0 for success, 1 if no ghost scrambles exist).

    """
    cube = options.cube

    rows: list[tuple[int, str, str, int, int]] = []
    for key in ghost_keys(cube):
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
                key,
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

    rows.sort(key=lambda row: (row[4] == 0, row[4], row[0]))

    ids = reference_ids(
        load_all_solves(
            cube,
            options.include_sessions,
            options.exclude_sessions,
            options.devices,
        ),
    )

    console.print('[title]Ghost Library[/title]')
    for date, key, scramble, attempts, best in rows:
        solve_id = ids.get(date, 0)
        label = f'#{ solve_id }' if solve_id else '—'
        console.print(
            f'[round]{ label:>5}[/round] '
            f'[consign]{ key[:KEY_SHORT] }[/consign] '
            f'[time]{ format_time(best) }[/time] '
            f'[stats]{ attempts:>3} attempts[/stats] '
            f'[moves]{ scramble }[/moves]',
        )
    return 0


async def ghost(options: Namespace) -> int:  # noqa: C901, PLR0911, PLR0912
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

    if not reference.solve.analysable:
        console.print(
            f'🤔 Reference { reference.label } has no reconstruction to '
            'race (DNF or not analysable).',
            style='warning',
        )
        return 1

    key = reference.key
    scramble_str = str(reference.solve.scramble)

    try:
        replay = load_scramble_replay(
            options.replay,
            scramble_str,
        )
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return 1

    history = load_solves(cube, key, directory=GHOSTS_DIRECTORY)
    stack = build_race_stack(reference.solve, history, key)
    ghost_solve = select_ghost(stack, options)

    console.print(ghost_header(reference.label, ghost_solve))

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
                f'[title]Summary on Ghost { reference.label }[/title]',
            )

            stats = SolveStatisticsReporter(cube, instance.stack)
            stats.print_summary()
            stats.graph('Tendency')

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
        return 1
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
