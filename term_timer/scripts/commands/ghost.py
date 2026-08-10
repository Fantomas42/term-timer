"""Ghost racing command."""
import operator
from argparse import Namespace
from random import Random
from typing import Final
from typing import NamedTuple

from term_timer.constants import GHOST_EMOJI
from term_timer.constants import GHOSTS_DIRECTORY
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import scramble_to_key
from term_timer.interface.console import console
from term_timer.scripts.commands.session import build_race_timer
from term_timer.scripts.commands.session import print_scramble_details
from term_timer.scripts.commands.session import print_scramble_review
from term_timer.scripts.commands.session import race_header
from term_timer.scripts.commands.session import run_seeded_race
from term_timer.solve import Solve

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


def ghost_stack(
        options: Namespace,
) -> tuple[GhostReference, list[Solve]] | None:
    """
    Resolve the raced scramble and load the attempts stored on it.

    Prints a warning and returns None when the reference resolves to
    nothing or when the scramble has never been raced.

    Returns:
        The reference and its attempts, or None.

    """
    reference = load_reference(options)
    if reference is None:
        return None

    stack = load_solves(
        options.cube, reference.key, directory=GHOSTS_DIRECTORY,
    )
    if not stack:
        console.print(
            '🤔 No ghost attempts recorded yet for this scramble.',
            style='warning',
        )
        return None

    return reference, stack


def ghost_review(options: Namespace) -> int:
    """
    Show stats, listing, graph and diagnostics for a ghost file.

    Every attempt of the file races the same scramble, so the review
    closes on the doctor report of that scramble.

    Returns:
        Exit code (0 for success, 1 if the scramble has no attempts).

    """
    resolved = ghost_stack(options)
    if resolved is None:
        return 1

    reference, stack = resolved

    return print_scramble_review(
        options,
        stack,
        f'Summary on Ghost { reference.label }',
    )


def ghost_detail(options: Namespace) -> int:
    """
    Show the detail of the ghost attempts named by --detail.

    Returns:
        Exit code (0 for success, 1 if the scramble has no attempts or
        an id names no attempt).

    """
    resolved = ghost_stack(options)
    if resolved is None:
        return 1

    return print_scramble_details(options, resolved[1])


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

    console.print(
        f'[title]Ghost Library for { cube }x{ cube }x{ cube}[/title]',
    )
    for date, key, scramble, attempts, best in rows:
        solve_id = ids.get(date, 0)
        label = f'#{ solve_id }' if solve_id else '---'
        console.print(
            f'[localhost]{ label:>5}[/localhost] '
            f'[comment]{ key[:KEY_SHORT] }[/comment] '
            f'[time]{ format_time(best) }[/time] '
            f'[stats]{ attempts:>3} attempts[/stats] '
            f'[consign]{ scramble }[/consign]',
        )
    return 0


def ghost_report(options: Namespace) -> int | None:
    """
    Answer the reading modes of the command, before any race.

    The library comes first, then the detail of an attempt, then the
    review it is read from: naming an attempt implies the review it
    belongs to.

    Returns:
        The exit code of the mode asked for, or None when none is and
        the command has a race to run.

    """
    if options.summary:
        return ghost_summary(options)

    if options.detail:
        return ghost_detail(options)

    if options.review:
        return ghost_review(options)

    return None


async def ghost(options: Namespace) -> int:
    """
    Race a live solve against a recorded ghost on the same scramble.

    Returns:
        Exit code (0 for success, 1 on resolution errors).

    """
    cube = options.cube

    report = ghost_report(options)
    if report is not None:
        return report

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
    history = load_solves(cube, key, directory=GHOSTS_DIRECTORY)

    instance = build_race_timer(
        options,
        session=key,
        scramble=str(reference.solve.scramble),
        stack=build_race_stack(reference.solve, history, key),
        rng=Random(),  # noqa: S311
        save_directory=GHOSTS_DIRECTORY,
    )
    if instance is None:
        return 1

    console.print(
        race_header(
            f'[ghost]{ GHOST_EMOJI } Ghost Race - '
            f'Scramble { reference.label }[/ghost]',
            instance.ghost,
        ),
    )

    return await run_seeded_race(
        instance,
        options,
        f'Summary on Ghost { reference.label }',
    )
