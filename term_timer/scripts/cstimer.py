import json
import operator
import sys
from datetime import datetime
from pathlib import Path

from term_timer.argparser import ArgumentParser
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.in_out import load_solves
from term_timer.solve import Solve


def date_to_ts(date: str) -> int:
    date_format = '%Y-%m-%d %H:%M:%S'
    dt = datetime.strptime(date, date_format)  # noqa: DTZ007

    return dt.timestamp()


def time_to_ns(time: str) -> int:
    minutes_str = '0'
    reste = time
    if ':' in time:
        minutes_str, reste = time.split(':')

    seconds_str, centiseconds_str = reste.split('.')

    minutes = int(minutes_str)
    seconds = int(seconds_str)
    centiseconds = int(centiseconds_str)

    total_seconds = minutes * 60 + seconds + centiseconds / 100

    return int(total_seconds * SECOND)


def import_csv(export_path: Path, solves: list) -> str:
    with export_path.open() as fd:
        lines = fd.readlines()

    for line in lines[1:]:
        flag = ''
        (_i, time_corrected, _comment, scramble, date, time) = line.split(';')
        date = date_to_ts(date)
        time = time_to_ns(time)

        if '+' in time_corrected:
            flag = PLUS_TWO
        elif 'DNF(' in time_corrected:
            flag = DNF

        solves.append(
            Solve(
                date, time,
                scramble,
                flag,
                'csTimer',
            ).as_save,
        )

    solves = sorted(solves, key=operator.itemgetter('date'))

    return json.dumps(solves, indent=1)


def import_json(export_path: Path, solves: []) -> str:
    """
    Advanced import for 3x3x3 bluetooth cube
    """
    with export_path.open() as fd:
        data = json.load(fd)

    properties = data['properties']
    session_data = json.loads(properties['sessionData'])

    for session_key in data:
        if 'session' not in session_key:
            continue

        if not len(data[session_key]):
            continue

        property_key = session_key.replace('session', '')
        session_property = session_data[property_key]

        scramble_type = session_property.get('opt', {}).get('scrType', '')

        if scramble_type:
            continue

        for solve in data[session_key]:
            if len(solve) != 5:
                continue

            flag, time = solve[0]
            scramble = solve[1]
            date = solve[3]
            moves = solve[4][0]

            if flag == -1:
                flag = DNF
            elif flag == 2000:
                flag = PLUS_TWO
            else:
                flag = ''

            device = ''
            if 'moyu' in session_property['name'].lower():
                device = 'WCU_MY32_A6A7'
            else:
                device = 'GAN12uiFp-2EE'

            solves.append(
                Solve(
                    date,
                    time * MS_TO_NS_FACTOR,
                    scramble,
                    flag,
                    'csTimer',
                    device,
                    moves,
                ).as_save,
            )

    solves = sorted(solves, key=operator.itemgetter('date'))

    return json.dumps(solves, indent=1)


def main() -> None:
    parser = ArgumentParser(
        description='Import CSTimer solves into term-timer',
    )
    parser.add_argument(
        'export',
        help='CSTimer CSV or TXT file to import',
    )
    parser.add_argument(
        '-m', '--merge',
        nargs='?',
        type=int,
        default=0,
        help='Merge within existing data',
    )

    options = parser.parse_args(sys.argv[1:])

    export = options.export
    merge = options.merge
    source = []
    for solve in (merge and load_solves(merge)) or []:
        source.append(solve.as_save)
    export_path = Path(export)

    if export.endswith('.csv'):
        print(import_csv(export_path, source))

    elif export.endswith('.txt'):
        print(import_json(export_path, source))

    return 0
