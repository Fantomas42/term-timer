"""Load and save solve data to and from JSON files."""
import json
import operator
import re
from pathlib import Path

from cubing_algs.algorithm import Algorithm
from cubing_algs.exceptions import InvalidMoveError
from cubing_algs.parsing import parse_moves

from term_timer.constants import SAVE_DIRECTORY
from term_timer.solve import Solve
from term_timer.solve import SolveData

SCRAMBLE_LINE = re.compile(r'Scramble #\d+:\s*(.+?)(?:\s*//.*)?$')


def load_solves(cube: int, session: str) -> list[Solve]:
    """
    Load solves from file for given cube size and session.

    Returns:
        List of Solve objects loaded from the JSON file.

    """
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    if source.exists():
        with source.open('r', encoding='utf-8') as fd:
            datas: list[SolveData] = json.load(fd)

        return [
            Solve(
                **data,
                session=session,
                cube_size=cube,
                solve_id=i + 1,
            )
            for i, data in enumerate(datas)
        ]

    return []


def load_all_solves(cube: int,
                    includes: list[str],
                    excludes: list[str],
                    devices: list[str]) -> list[Solve]:
    """
    Load all solves from multiple sessions with filters.

    Returns:
        Deduplicated and sorted list of Solve objects from all sessions.

    """
    if len(includes) == 1:
        return load_solves(cube, includes[0])

    prefix = f'{ cube }x{ cube }x{ cube }-'

    solves = []
    sessions = ['default'] + [
        f.name.split(prefix, 1)[1].replace('.json', '')
        for f in SAVE_DIRECTORY.iterdir()
        if (
                f.is_file()
                and f.name.startswith(prefix)
                and not f.name.endswith('~')
        )
    ]

    if includes:
        for session_name in sessions:
            if session_name in includes:
                solves.extend(
                    load_solves(cube, session_name),
                )
    else:
        for session_name in sessions:
            if session_name not in excludes:
                solves.extend(
                    load_solves(cube, session_name),
                )

    if devices:
        solves = [solve for solve in solves if solve.device in devices]

    uniques = {}
    for solve in solves:
        uniques[solve.date] = solve

    return sorted(uniques.values(), key=operator.attrgetter('date'))


def save_solves(cube: int, session: str, solves: list[Solve]) -> bool:
    """
    Save solves to file for given cube size and session.

    Returns:
        True if save was successful.

    """
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    data = [s.as_save for s in solves]

    dumped = json.dumps(data, indent=1)

    if not SAVE_DIRECTORY.exists():
        SAVE_DIRECTORY.mkdir()

    with source.open('w+', encoding='utf-8') as fd:
        fd.write(dumped)

    return True


def load_scrambles(path: Path) -> list[Algorithm]:
    """
    Load scrambles from a file.

    Supports two formats:
    - term-timer format: "Scramble #1: MOVES // HTM"
    - Plain format: "MOVES" (one per line)

    Args:
        path: Path to the file containing scrambles.

    Returns:
        List of Algorithm objects parsed from the file.

    """
    scrambles: list[Algorithm] = []

    if not path.exists():
        return scrambles

    content = path.read_text(encoding='utf-8')

    for raw_line in content.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        moves_str = line
        matching = SCRAMBLE_LINE.match(line)
        if matching:
            moves_str = matching.group(1).strip()

        try:
            algorithm = parse_moves(moves_str, secure=False)
            scrambles.append(algorithm)
        except InvalidMoveError:
            continue

    return scrambles
