from term_timer.constants import SAVE_FILE
from term_timer.formatter import format_duration
from term_timer.solve import Solve


def load_solves():
    if SAVE_FILE.exists():
        with SAVE_FILE.open() as fd:
            datas = fd.readlines()
        return [
            Solve(*data.split(';')[1:-1])
            for data in datas
        ]

    return []


def save_solves(solves):
    with SAVE_FILE.open('w+') as fd:
        for s in solves:
            fd.write(
                f'{ format_duration(s.elapsed_time) };'
                f'{ s.start_time };{ s.end_time };'
                f'{ s.scramble};{ s.flag };\n',
            )
