import json
import operator
from datetime import datetime
from pathlib import Path
from typing import Any

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.solve import SolveData


class Importer:

    def date_to_ts(self, date: str) -> float:
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

    def cubeast_csv(self, data: list[str]) -> list[SolveData]:
        solves: list[SolveData] = []

        for _line in data[1:]:
            line = _line.split(',')

            date_str = line[1][:-4]
            dnf = line[2]
            time_str = line[3]
            device = line[6]
            moves = line[14]
            scramble = line[19]

            date = self.date_to_ts(date_str)

            flag: SolveFlag = ''
            if dnf == 'true':
                flag = DNF

            fixed_moves: list[str] = []
            for move_raw in moves.split(' '):
                if move_raw:
                    move, time = move_raw.split('[')
                    time = time.replace(']', '')
                    fixed_moves.append(f'{ move }@{ time }')

            solves.append(
                Solve(
                    date,
                    int(time_str) * MS_TO_NS_FACTOR,
                    scramble,
                    flag,
                    'Cubeast',
                    device,
                    'import_cubeast_csv',
                    moves=' '.join(fixed_moves),
                ).as_save,
            )

        return solves

    def cstimer_csv(self, data: list[str]) -> list[SolveData]:
        solves: list[SolveData] = []

        for line in data[1:]:
            flag: SolveFlag = ''
            (
                _i, time_corrected, _comment, scramble, date_str, time_str,
            ) = line.split(';')
            date = self.date_to_ts(date_str)
            time = self.time_to_ns(time_str)

            if '+' in time_corrected:
                flag = PLUS_TWO
            elif 'DNF(' in time_corrected:
                flag = DNF

            solves.append(
                Solve(
                    date,
                    time,
                    scramble,
                    flag,
                    'csTimer',
                    '',
                    'import_cstimer_csv',
                ).as_save,
            )

        return solves

    def cstimer_json(self, data: dict[str, Any]) -> list[SolveData]:
        solves: list[SolveData] = []
        properties: dict[str, Any] = data['properties']
        session_data: dict[str, Any] = json.loads(properties['sessionData'])

        for session_key, session_values in data.items():
            if 'session' not in session_key:
                continue

            if not len(session_values):
                continue

            property_key = session_key.replace('session', '')
            session_property: dict[str, Any] = session_data[property_key]

            scramble_type: str = session_property.get(
                'opt', {},
            ).get(
                'scrType', '',
            )

            if scramble_type:
                continue

            for solve in session_values:
                if len(solve) != 5:
                    continue

                flag_raw: int | str
                time_raw: int
                flag_raw, time_raw = solve[0]
                scramble: str = solve[1]
                date: float = solve[3]
                moves: str = solve[4][0]

                flag: SolveFlag
                if flag_raw == -1:
                    flag = DNF
                elif flag_raw == 2000:
                    flag = PLUS_TWO
                else:
                    flag = ''

                device = ''

                solves.append(
                    Solve(
                        date,
                        time_raw * MS_TO_NS_FACTOR,
                        scramble,
                        flag,
                        'csTimer',
                        device,
                        'import_cstimer_json',
                        moves=moves,
                    ).as_save,
                )

        return solves

    def import_file(self, source: str) -> int:
        source_path = Path(source)

        solves: list[SolveData] | None = None

        if source.endswith(('.json', '.txt')):
            with source_path.open() as fd:
                data: dict[str, Any] = json.load(fd)

            solves = self.cstimer_json(data)

        elif source.endswith('.csv'):
            with source_path.open() as fd:
                data_lines: list[str] = fd.readlines()

            if 'No.;' in data_lines[0]:
                solves = self.cstimer_csv(data_lines)
            elif 'id,' in data_lines[0]:
                solves = self.cubeast_csv(data_lines)

        if solves is None:
            console.print('Invalid export format', style='warning')
            return 1

        solves = sorted(solves, key=operator.itemgetter('date'))

        out = json.dumps(solves, indent=1)

        print(out)

        return 0
