"""Load and save solve data to and from JSON files."""
import json
import operator
import re
from hashlib import blake2s
from pathlib import Path

from cubing_algs.algorithm import Algorithm
from cubing_algs.exceptions import InvalidMoveError
from cubing_algs.parsing import parse_moves
from fsrs import Card
from fsrs import State

from term_timer.constants import DAILY_DIRECTORY
from term_timer.constants import SOLVES_DIRECTORY
from term_timer.constants import TRAININGS_DIRECTORY
from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import CaseTrainingData
from term_timer.fsrs.storage import Trainings
from term_timer.solve import Solve
from term_timer.solve import SolveData

SCRAMBLE_LINE = re.compile(r'Scramble #\d+:\s*(.+?)(?:\s*//.*)?$')


def scramble_to_key(scramble: str) -> str:
    """
    Turn a scramble string into a filesystem- and URL-safe session key.

    The scramble is digested so the key stays short whatever the cube
    size: spelling the moves out overflows the 255 bytes a filename
    allows from the 6x6x6 up. The digest is taken on the raw text, with
    no normalization, so two textually different but equivalent
    scrambles still map to different keys.

    Returns:
        The transformed session key (e.g. ``"c3fd54cd2d5f8b4f"``).

    """
    return blake2s(scramble.encode(), digest_size=8).hexdigest()


def fsrs_card_from_data(raw: 'CaseTrainingData') -> Card | None:
    """
    Deserialize an optional FSRS card from raw training data.

    Returns:
        Card instance if fsrs data is present, None otherwise.

    """
    if 'fsrs' not in raw:
        return None

    card = Card.from_dict(raw['fsrs'])
    if card.state == State.Review:
        # Temporary repair, to remove once existing training files have
        # been re-saved: legacy files serialized step 0 instead of None,
        # violating the py-fsrs invariant for Review cards.
        card.step = None

    return card


def load_solves(
        cube: int,
        session: str,
        directory: Path = SOLVES_DIRECTORY,
) -> list[Solve]:
    """
    Load solves from file for given cube size and session.

    Returns:
        List of Solve objects loaded from the JSON file.

    """
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = directory / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

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


def load_all_solves(
        cube: int,
        includes: list[str],
        excludes: list[str],
        devices: list[str],
        directory: Path = SOLVES_DIRECTORY,
) -> list[Solve]:
    """
    Load all solves from multiple sessions with filters.

    Returns:
        Deduplicated and sorted list of Solve objects from all sessions.

    """
    if len(includes) == 1:
        solves = load_solves(cube, includes[0], directory=directory)
    else:
        prefix = f'{ cube }x{ cube }x{ cube }-'

        solves = []
        sessions = ['default'] + [
            f.name.split(prefix, 1)[1].replace('.json', '')
            for f in directory.iterdir()
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
                        load_solves(cube, session_name, directory=directory),
                    )
        else:
            for session_name in sessions:
                if session_name not in excludes:
                    solves.extend(
                        load_solves(cube, session_name, directory=directory),
                    )

    if devices:
        solves = [solve for solve in solves if solve.device in devices]

    uniques = {}
    for solve in solves:
        uniques[solve.date] = solve

    return sorted(uniques.values(), key=operator.attrgetter('date'))


def load_all_daily_solves(cube: int) -> list[Solve]:
    """
    Load all solves from all daily sessions.

    Returns:
        Sorted list of Solve objects from every daily session file.

    """
    prefix = f'{ cube }x{ cube }x{ cube }-'

    solves = []
    if DAILY_DIRECTORY.exists():
        for f in sorted(DAILY_DIRECTORY.iterdir()):
            is_session = (
                f.is_file()
                and f.name.startswith(prefix)
                and not f.name.endswith('~')
            )
            if is_session:
                session = f.name.split(prefix, 1)[1].replace('.json', '')
                solves.extend(
                    load_solves(cube, session, directory=DAILY_DIRECTORY),
                )

    return sorted(solves, key=operator.attrgetter('date'))


def save_solves(
        cube: int,
        session: str,
        solves: list[Solve],
        directory: Path = SOLVES_DIRECTORY,
) -> bool:
    """
    Save solves to file for given cube size and session.

    Returns:
        True if save was successful.

    """
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = directory / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    data = [s.as_save for s in solves]

    dumped = json.dumps(data, indent=1)

    with source.open('w+', encoding='utf-8') as fd:
        fd.write(dumped)

    return True


def load_trainings(method: str, step: str) -> Trainings:
    """
    Load trainings from file for given method and step.

    Returns:
        Trainings object containing all training data for the method/step,
        with methods to add new timings and serialize back to JSON.

    """
    source_directory = TRAININGS_DIRECTORY / method
    source_directory.mkdir(parents=True, exist_ok=True)

    source = source_directory / f'{ step }.json'

    cases: dict[str, CaseTraining] = {}

    if source.exists():
        with source.open('r', encoding='utf-8') as fd:
            raw_data: dict[str, CaseTrainingData] = json.load(fd)

        cases = {
            case_code: CaseTraining(
                code=case_code,
                last_date=data['last_date'],
                timings=data['timings'],
                fsrs_card=fsrs_card_from_data(data),
                solution=data.get('solution', ''),
            )
            for case_code, data in raw_data.items()
        }

    return Trainings(method=method, step=step, cases=cases)


def save_trainings(trainings: Trainings) -> bool:
    """
    Save trainings to file for given method and step.

    Returns:
        True if save was successful.

    """
    source_directory = TRAININGS_DIRECTORY / trainings.method
    source_directory.mkdir(parents=True, exist_ok=True)

    source = source_directory / f'{ trainings.step }.json'

    data = trainings.as_save()

    dumped = json.dumps(data, indent=1, sort_keys=True)

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
            algorithm = parse_moves(moves_str, trust_input=False)
            scrambles.append(algorithm)
        except InvalidMoveError:
            continue

    return scrambles
