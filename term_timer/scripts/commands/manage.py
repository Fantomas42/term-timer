"""Manage command."""
from argparse import Namespace
from random import Random

from term_timer.interface.console import console
from term_timer.manage import ScrambleManager
from term_timer.manage import SessionManager
from term_timer.manage import SolveManager


def manage(command: str, options: Namespace) -> int:
    """
    Manage solve data.

    Returns:
        Exit code (0 for success).

    """
    if command == 'index':
        session_manager = SessionManager()
        session_manager.index()
        return 0

    if command == 'merge':
        session_manager = SessionManager()
        session_manager.merge(options.sessions)
        return 0

    cube = options.cube

    if command == 'edit':
        if not options.flag and not options.comment:
            console.print(
                '🤔 Nothing to edit, use --flag or --comment at least.',
                style='warning',
            )
            return 0

        for solve_id in options.solves:
            solve_manager = SolveManager(cube, options.session, solve_id)
            solve_manager.display_solve()

            if options.flag:
                solve_manager.update_flag(options.flag, yes=options.yes)
            if options.comment:
                solve_manager.update_comment(options.comment, yes=options.yes)

    if command == 'delete':
        solve_manager = SolveManager(cube, options.session, options.solve)
        solve_manager.display_solve()
        solve_manager.delete()

    if command == 'scramble':
        rng = Random(options.seed) if options.seed else Random()  # noqa: S311

        scramble_manager = ScrambleManager(
            cube_size=cube,
            scrambles=options.scrambles,
            iterations=options.iterations,
            easy_cross=options.easy_cross,
            x_cross=options.x_cross,
            edges_oriented=options.edges_oriented,
            show_cube=options.show_cube,
            linear=options.linear,
            no_color=options.no_color,
            output_format=options.format,
            seed=options.seed,
            rng=rng,
        )
        scramble_manager.run()

    return 0
