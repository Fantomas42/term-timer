from datetime import datetime
from datetime import timezone

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_time


class Solve:
    def __init__(self,
                 date: datetime,
                 time: int | str,
                 scramble: str, flag: str = '',
                 device: str = '',
                 moves: list[dict[str, str]] | None = None):
        self.date = int(date)
        self.time = int(time)
        self.scramble = scramble
        self.flag = flag
        self.moves = moves
        self.device = device

    @property
    def final_time(self) -> int:
        if self.flag == PLUS_TWO:
            return self.time + (2 * SECOND)
        if self.flag == DNF:
            return 0

        return self.time

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.date, tz=timezone.utc)   # noqa: UP017

    def as_save(self):
        return {
            'date': self.date,
            'time': self.time,
            'scramble': self.scramble,
            'flag': self.flag,
            'device': self.device,
            'moves': self.moves or [],
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
