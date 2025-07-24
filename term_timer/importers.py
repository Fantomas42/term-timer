import json
import operator
from datetime import datetime
from pathlib import Path

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.interface.console import console
from term_timer.solve import Solve


class Importer:

    def date_to_ts(self, date: str) -> int:
        date_format = '%Y-%m-%d %H:%M:%S'
        dt = datetime.strptime(date, date_format)  # noqa: DTZ007

        return dt.timestamp()

    def time_to_ns(self, time: str) -> int:
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

    def cubeast_csv(self, data):
        solves = []

        for _line in data[1:]:
            line = _line.split(',')

            date = line[1][:-4]
            dnf = line[2]
            time = line[3]
            device = line[6]
            moves = line[14]
            scramble = line[19]

            date = self.date_to_ts(date)

            flag = ''
            if dnf == 'true':
                flag = DNF

            fixed_moves = []
            for move_raw in moves.split(' '):
                if move_raw:
                    move, time = move_raw.split('[')
                    time = time.replace(']', '')
                    fixed_moves.append(f'{ move }@{ time }')

            solves.append(
                Solve(
                    date,
                    int(time) * MS_TO_NS_FACTOR,
                    scramble,
                    flag,
                    'Cubeast',
                    device,
                    'import_cubeast_csv',
                    ' '.join(fixed_moves),
                ).as_save,
            )

        return solves

    def cstimer_csv(self, data):
        solves = []

        for line in data[1:]:
            flag = ''
            (
                _i, time_corrected, _comment, scramble, date, time,
            ) = line.split(';')
            date = self.date_to_ts(date)
            time = self.time_to_ns(time)

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
                    '',
                    'import_cstimer_csv',
                ).as_save,
            )

        return solves

    def cstimer_json(self, data):
        solves = []
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

                solves.append(
                    Solve(
                        date,
                        time * MS_TO_NS_FACTOR,
                        scramble,
                        flag,
                        'csTimer',
                        device,
                        'import_cstimer_json',
                        moves,
                    ).as_save,
                )

        return solves

    def import_file(self, source: str) -> int:
        source_path = Path(source)

        solves = None

        if source.endswith(('.json', '.txt')):
            with source_path.open() as fd:
                data = json.load(fd)

            solves = self.cstimer_json(data)

        elif source.endswith('.csv'):
            with source_path.open() as fd:
                data = fd.readlines()

            if 'No.;' in data[0]:
                solves = self.cstimer_csv(data)
            elif 'id,' in data[0]:
                solves = self.cubeast_csv(data)

        if solves is None:
            console.print('Invalid export format', style='warning')
            return 1

        solves = sorted(solves, key=operator.itemgetter('date'))

        out = json.dumps(solves, indent=1)

        print(out)

        return 0
