from datetime import datetime
from datetime import timezone
from functools import cached_property

from cubing_algs.algorythm import Algorythm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.optimize import optimize_do_undo_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.optimize import optimize_repeat_three_moves

from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import format_time


class Solve:
    def __init__(self,
                 date: int, time: int,
                 scramble: str, flag: str = '',
                 device: str = '',
                 moves: list[dict[str, str]] | None = None):
        self.date = int(date)
        self.time = int(time)
        self.scramble = scramble
        self.flag = flag
        self.device = device
        self.raw_moves = moves

    @cached_property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(
            self.date, tz=timezone.utc,  # noqa: UP017
        )

    @cached_property
    def final_time(self) -> int:
        if self.flag == PLUS_TWO:
            return self.time + (2 * SECOND)
        if self.flag == DNF:
            return 0

        return self.time

    @cached_property
    def move_times(self) -> list[str, int]:
        return [
            move_time.split('@')
            for move_time in self.raw_moves.split(' ')
            if move_time
        ]

    @cached_property
    def solution(self) -> Algorythm:
        return parse_moves([m[0] for m in self.move_times])

    @cached_property
    def solution_tps(self) -> float:
        return len(self.solution) / (self.time / SECOND)

    @cached_property
    def reconstructed_solution(self) -> list[str, int]:
        return self.solution.transform(
            optimize_double_moves,  # + slicing + rotations
        )

    @cached_property
    def reconstructed_solution_tps(self) -> float:
        return len(self.reconstructed_solution) / (self.time / SECOND)

    @cached_property
    def missed_moves(self) -> int:
        return len(self.solution) - len(
            self.solution.transform(
                optimize_do_undo_moves,
                optimize_repeat_three_moves,
            ),
        )

    @property
    def as_save(self):
        return {
            'date': self.date,
            'time': self.time,
            'scramble': self.scramble,
            'flag': self.flag,
            'device': self.device,
            'moves': self.raw_moves or [],
        }

    def __str__(self) -> str:
        return f'{ format_time(self.time) }{ self.flag }'
