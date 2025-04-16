import json
import operator
import sys
from datetime import datetime
from pathlib import Path

from term_timer.argparser import ArgumentParser
from term_timer.constants import DNF
from term_timer.in_out import load_solves
from term_timer.solve import Solve


def date_to_ts(date: str) -> int:
    date_format = '%Y-%m-%d %H:%M:%S'
    dt = datetime.strptime(date[:-4], date_format)  # noqa: DTZ007

    return dt.timestamp()


def import_csv(export_path: Path, solves: list) -> str:
    with export_path.open() as fd:
        lines = fd.readlines()

    for _line in lines[1:]:
        line = _line.split(',')

        date = line[1]
        dnf = line[2]
        time = line[3]
        device = line[6]
        moves = line[14]
        scramble = line[19]

        date = date_to_ts(date)

        flag = ''
        if dnf == 'true':
            flag = DNF

        if 'moyu' in device.lower():
            device = 'WCU_MY32_A6A7'
        else:
            device = 'GAN12uiFp-2EE'

        fixed_moves = []
        for move_raw in moves.split(' '):
            if move_raw:
                move, time = move_raw.split('[')
                time = time.replace(']', '')
                fixed_moves.append(f'{ move }@{ time }')

        solves.append(
            Solve(
                date,
                int(time) * 1_000_000,
                scramble,
                flag,
                'Cubeast',
                device,
                ' '.join(fixed_moves),
            ).as_save,
        )

    solves = sorted(solves, key=operator.itemgetter('date'))

    return json.dumps(solves, indent=1)


def main() -> None:
    parser = ArgumentParser(
        description='Import Cubeast solves into term-timer',
    )
    parser.add_argument(
        'export',
        help='Cubeast CSV file to import',
    )
    parser.add_argument(
        '-m', '--merge',
        nargs='?',
        type=int,
        default=0,
        help='Merge within existing data',
    )

    options = parser.parse_args(sys.argv[1:])

    merge = options.merge
    source = []
    for solve in (merge and load_solves(merge)) or []:
        source.append(solve.as_save)

    export_path = Path(options.export)

    print(import_csv(export_path, source))

    return 0
