from term_timer.console import console
from term_timer.formatter import computing_padding
from term_timer.formatter import format_time
from term_timer.solve import Solve


class Listing:
    def __init__(self, stack: list[Solve]):
        self.stack = stack

    def resume(self, limit: int) -> None:
        if not self.stack:
            console.print('[warning]No saved solves yet.[/warning]')
            return

        size = len(self.stack)
        max_count = computing_padding(size) + 1

        for i in range(1, limit + 1):
            if i > size:
                return

            solve = self.stack[-i]
            index = f'#{ size - i + 1}'

            console.print(
                f'[stats]{ index:{" "}>{max_count}}[/stats]',
                f'[result]{ format_time(solve.elapsed_time) }[/result]',
                f'[consign]{ solve.scramble }[/consign]',
                f'[result]{ solve.flag }[/result]',
        )
