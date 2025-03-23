from datetime import datetime

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_time


class Solve:
    def __init__(self, start_time: int | str, end_time: int | str,
                 scramble: str, flag: str = ''):
        self.start_time = int(start_time)
        self.end_time = int(end_time)
        self.scramble = scramble
        self.flag = flag

        self.elapsed_time = self.end_time - self.start_time

    @property
    def final_time(self) -> int:
        elapsed = self.elapsed_time

        if self.flag == PLUS_TWO:
            return elapsed + (2 * SECOND)
        if self.flag == DNF:
            return 0

        return elapsed

    @property
    def start_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.start_time // SECOND)   # noqa: DTZ006

    def __str__(self) -> str:
        return f'{ format_time(self.elapsed_time) }{ self.flag }'
