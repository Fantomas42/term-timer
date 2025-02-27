import logging
import sys
from argparse import ArgumentParser
from random import seed

from term_timer.console import console
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.list import Listing
from term_timer.stats import Statistics
from term_timer.timer import Timer


def main() -> int:
    parser = ArgumentParser(
        description='3x3 timer',
    )
    parser.add_argument(
        'scrambles',
        nargs='?',
        help='Number of scrambles',
        default=0,
        type=int,
    )
    parser.add_argument(
        '-c', '--show-cube',
        help='Show the cube scrambled',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '-p', '--puzzle',
        help='Size of the puzzle',
        default=3,
        type=int,
    )
    parser.add_argument(
        '-i', '--countdown',
        help='Countdown for inspection time',
        default=0,
        type=int,
    )
    parser.add_argument(
        '-b', '--metronome',
        help='Make a beep with tempo',
        default=0,
        type=float,
    )
    parser.add_argument(
        '-f', '--free-play',
        help='Disable recording of solves',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '-s', '--seed',
        help='Seed of random moves',
    )
    parser.add_argument(
        '-n', '--iterations',
        help='Iterations of random moves',
        default=0,
        type=int,
    )
    parser.add_argument(
        '-m', '--mode',
        help='Mode of the scramble',
        default='default',
    )
    parser.add_argument(
        '--stats',
        help='Show the statistics',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--list',
        help='Show the last solves',
        default=0,
        type=int,
    )

    options = parser.parse_args(sys.argv[1:])

    logging.disable(logging.INFO)

    puzzle = options.puzzle
    if options.stats:
        session_stats = Statistics(puzzle, load_solves(puzzle))
        session_stats.resume('Global ')
        return 0

    if options.list:
        session_list = Listing(load_solves(puzzle))
        session_list.resume(options.list)
        return 0

    free_play = options.free_play
    if options.seed or options.iterations or options.mode != 'default':
        free_play = True

    if free_play:
        stack = []
        console.print(
            ':lock: Mode Free Play is active, solves will not be recorded !',
            style='warning',
        )
    else:
        stack = load_solves(puzzle)

    if options.seed:
        seed(options.seed)

    solves_done = 0

    while 42:
        timer = Timer(
            puzzle=puzzle,
            mode=options.mode,
            iterations=options.iterations,
            free_play=free_play,
            show_cube=options.show_cube,
            countdown=options.countdown,
            metronome=options.metronome,
            stack=stack,
        )

        done = timer.start()
        stack = timer.stack

        if done:
            solves_done += 1

            if options.scrambles and solves_done >= options.scrambles:
                break
        else:
            break

    if not free_play:
        save_solves(puzzle, stack)

    if len(stack) > 1:
        session_stats = Statistics(puzzle, stack)
        session_stats.resume((free_play and 'Session ') or 'Global ')

    return 0
