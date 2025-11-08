"""Solve and session management utilities for editing and deleting solves."""

from rich import box
from rich.table import Table

from term_timer.constants import CUBE_SIZES
from term_timer.constants import DNF
from term_timer.constants import PLUS_TWO
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import Statistics


class SolveManager:
    def __init__(self, cube: int, session: str, solve_id: int) -> None:
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

    def update(self, flag: SolveFlagInput) -> None:
        if self.solve is None:
            return

        if self.confirm(
                f'Are you sure to mark this solve as "{ flag }" ?',
                self.solve,
        ):
            normalized_flag: SolveFlag = '' if flag == 'OK' else flag

            self.stack[self.solve_index].flag = normalized_flag
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


class SessionManager:

    def index(self) -> None:
        sessions: dict[int, dict[str, list[Solve]]] = {}

        for cube in CUBE_SIZES:
            solves = load_all_solves(cube, [], [], [])
            sessions[cube] = {}
            for solve in solves:
                sessions[cube].setdefault(
                    solve.session, [],
                ).append(
                    solve,
                )

        for cube, session_solves in sessions.items():
            if not session_solves:
                continue

            table = Table(
                title=f'Cube { cube }x{ cube }x{ cube }',
                box=box.SIMPLE,
            )
            table.add_column('Name', width=30)
            table.add_column('Total', width=5, justify='right')
            table.add_column('Last solve', width=16)
            table.add_column('Best', width=10)

            names = sorted(session_solves.keys())

            for name in names:
                session = session_solves[name]
                stats = Statistics(session)
                last_solve_date = (
                    session[-1].datetime.astimezone().strftime(
                        '%Y-%m-%d %H:%M',
                    )
                )

                table.add_row(
                    f'[stats]{ name }[/stats] ',
                    f'[result]{ len(session_solves[name]) }[/result]',
                    f'[date]{ last_solve_date }[/date]',
                    f'[time]{ format_time(stats.best) }[/time]',
                )
            console.print(table)
