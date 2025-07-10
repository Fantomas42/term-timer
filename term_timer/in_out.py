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
    if len(includes) == 1:
        return load_solves(cube, includes[0])

    prefix = f'{ cube }x{ cube }x{ cube }-'

    solves = []
    sessions = ['default'] + [
        f.name.split(prefix, 1)[1].replace('.json', '')
        for f in SAVE_DIRECTORY.iterdir()
        if f.is_file() and f.name.startswith(prefix)
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
    if session == 'default':
        session = ''

    suffix = (session and f'-{ session }') or ''

    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }{ suffix }.json'

    data = []
    for s in solves:
        data.append(s.as_save)

    dumped = json.dumps(data, indent=1)

    with source.open('w+') as fd:
        fd.write(dumped)

    return True
