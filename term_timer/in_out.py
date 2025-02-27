from term_timer.constants import SAVE_DIRECTORY
from term_timer.formatter import format_duration
from term_timer.solve import Solve


def load_solves(puzzle: int) -> list[Solve]:
    source = SAVE_DIRECTORY / f'{ puzzle }x{ puzzle }x{ puzzle }.csv'

    if source.exists():
        with source.open() as fd:
            datas = fd.readlines()
        return [
            Solve(*data.split(';')[1:-1])
            for data in datas
        ]

    return []


def save_solves(puzzle: int, solves: list[Solve]) -> None:
    source = SAVE_DIRECTORY / f'{ puzzle }x{ puzzle }x{ puzzle }.csv'

    with source.open('w+') as fd:
        for s in solves:
            fd.write(
                f'{ format_duration(s.elapsed_time) };'
                f'{ s.start_time };{ s.end_time };'
                f'{ s.scramble};{ s.flag };\n',
            )
