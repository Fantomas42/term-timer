import json
import operator

from term_timer.constants import SAVE_DIRECTORY
from term_timer.solve import Solve


def load_solves(cube: int, session: str) -> list[Solve]:
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    if source.exists():
        with source.open() as fd:
            datas = json.load(fd)

        return [
            Solve(**data)
            for data in datas
        ]

    return []


def load_all_solves(cube: int, session: str) -> list[Solve]:
    if session:
        return load_solves(cube, session)

    prefix = f'{ cube }x{ cube }x{ cube }-'

    solves = []
    sessions = [''] + [
        f.name.split(prefix, 1)[1].replace('.json', '')
        for f in SAVE_DIRECTORY.iterdir()
        if f.is_file() and f.name.startswith(prefix)
    ]

    for session_name in sessions:
        solves.extend(
            load_solves(cube, session_name),
        )

    uniques = {}
    for solve in solves:
        uniques[solve.date] = solve

    return sorted(uniques.values(), key=operator.attrgetter('date'))


def save_solves(cube: int, session: str, solves: list[Solve]) -> bool:
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    data = []
    for s in solves:
        data.append(s.as_save)

    with source.open('w+') as fd:
        json.dump(data, fd, indent=1)

    return True
