import sys
from datetime import datetime
from pathlib import Path

from term_timer.argparser import ArgumentParser
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND


def date_to_ns(date: str) -> int:
    date_format = '%Y-%m-%d %H:%M:%S'
    dt = datetime.strptime(date, date_format)  # noqa: DTZ007

    timestamp_seconds = dt.timestamp()

    return int(timestamp_seconds * SECOND)


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


def import_csv() -> None:
    parser = ArgumentParser(
        description='Import CSTimer solves in CSV',
    )
    parser.add_argument(
        'export',
        help='CSTimer csv file to import',
    )

    options = parser.parse_args(sys.argv[1:])

    export_path = Path(options.export)

    with export_path.open() as fd:
        lines = fd.readlines()

    for line in lines[1:]:
        flag = ''
        (_i, time_corrected, _comment, scramble, date, time) = line.split(';')
        start_date = date_to_ns(date)
        end_date = start_date + time_to_ns(time)

        if '+' in time_corrected:
            flag = PLUS_TWO
        elif 'DNF(' in time_corrected:
            flag = DNF

        print(
            ';'.join(
                [
                    time.strip(),
                    str(start_date),
                    str(end_date),
                    scramble,
                    flag,
                    '',
                ],
            ),
        )
