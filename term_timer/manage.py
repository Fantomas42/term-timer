from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.formatter import format_time
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.solve import Solve


class SolveManager:
    def __init__(self, cube: int, session: str, solve_id: int):
        self.cube = cube
        self.session = session
        self.solve_id = solve_id

        self.solve_index = solve_id - 1
        self.stack = load_solves(cube, session)

        self.solve = self.get_solve()

    def get_solve(self) -> Solve | None:
        try:
            solve = self.stack[self.solve_index]
        except IndexError:
            console.print(
                f'Invalid solve #{ self.solve_id }',
                style='warning',
            )
            return None

        return solve

    def confirm(self, text: str, solve: Solve) -> bool:
        date = solve.datetime.astimezone().strftime('%Y-%m-%d %H:%M')

        flag_class = 'result'
        if solve.flag == DNF:
            flag_class = 'dnf'
        if solve.flag == PLUS_TWO:
            flag_class = 'plus-two'

        header = (
            f'[localhost][link={ solve.link_term_timer }]'
            f'Solve #{ self.solve_id}'
            '[/link][/localhost]'
        )

        console.print(
            header,
            f'[time]{ format_time(solve.time) }[/time]',
            f'[date]{ date }[/date]',
            f'[{ flag_class }]{ solve.flag }[/{ flag_class }]',
        )
        if solve.advanced:
            console.print(solve.report_line)

        text += ' (y/N)'
        console.print(text, style='confirm')
        confirm = input('')

        return confirm == 'y'

    def save(self) -> None:
        save_solves(self.cube, self.session, self.stack)

    def update(self, flag: str) -> None:
        if self.solve is None:
            return

        if self.confirm(
                f'Are you sure to mark this solve as "{ flag }" ?',
                self.solve,
        ):
            if flag == 'OK':
                flag = ''

            self.stack[self.solve_index].flag = flag
            self.save()

            console.print(
                f'Solve #{ self.solve_id } updated',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } untouched',
                style='caution',
            )

    def delete(self) -> None:
        if self.solve is None:
            return

        if self.confirm(
                'Are you sure you want to permanently delete this solve ?',
                self.solve,
        ):
            self.stack.pop(self.solve_index)
            self.save()

            console.print(
                f'Solve #{ self.solve_id } deleted',
                style='success',
            )
        else:
            console.print(
                f'Solve #{ self.solve_id } untouched',
                style='caution',
            )
