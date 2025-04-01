import json

from term_timer.constants import SAVE_DIRECTORY
from term_timer.solve import Solve


def load_solves(cube: int) -> list[Solve]:
    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }.json'

    if source.exists():
        with source.open() as fd:
            datas = json.load(fd)

        return [
            Solve(**data)
            for data in datas
        ]

    return []


def save_solves(cube: int, solves: list[Solve]) -> bool:
    source = SAVE_DIRECTORY / f'{ cube }x{ cube }x{ cube }.json'

    data = []
    for s in solves:
        data.append(s.as_save())

    breakpoint()

    with source.open('w+') as fd:
        json.dump(data, fd, indent=1)

    return True
