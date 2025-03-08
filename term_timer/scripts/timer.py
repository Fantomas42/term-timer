import logging
import sys
from random import seed

from term_timer.argparser import ArgumentParser
from term_timer.console import console
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.list import Listing
from term_timer.stats import Statistics
from term_timer.timer import Timer


def main() -> int:
    parser = ArgumentParser(
        description='Speed cubing timer on terminal',
        epilog='Have fun cubing !',
    )
    parser.add_argument(
        'solves',
        nargs='?',
        type=int,
        default=0,
        metavar='SOLVES',
        help=(
            'Specify the number of solves to record.\n'
            'Default: Infinite.'
        ),
    )
    parser.add_argument(
        '-c', '--show-cube',
        action='store_true',
        help=(
            'Display the cube in its scrambled state.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '-p', '--puzzle',
        type=int,
        choices=range(2, 8),
        default=3,
        metavar='PUZZLE',
        help=(
            'Set the size of the puzzle (2 to 7).\n'
            'Default: 3.'
        ),
    )
    parser.add_argument(
        '-i', '--countdown',
        type=int,
        default=0,
        metavar='SECONDS',
        help=(
            'Set the countdown timer for inspection time in seconds.\n'
            'Default: 0.'
        ),
    )
    parser.add_argument(
        '-b', '--metronome',
        type=float,
        default=0,
        metavar='TEMPO',
        help=(
            'Set a metronome beep at a specified tempo in seconds.\n'
            'Default: 0.0.'
        ),
    )
    parser.add_argument(
        '-f', '--free-play',
        action='store_true',
        help=(
            'Enable free play mode to disable recording of solves.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '-s', '--seed',
        default='',
        metavar='SEED',
        help=(
            'Provide a seed for random move generation '
            'to ensure repeatable scrambles.\n'
            'Default: None.'
        ),
    )
    parser.add_argument(
        '-n', '--iterations',
        type=int,
        default=0,
        metavar='ITERATIONS',
        help=(
            'Set the number of iterations of random moves.\n'
            'Default: Auto.'
        ),
    )
    parser.add_argument(
        '-m', '--mode',
        default='default',
        choices=('default', 'ec'),
        metavar='MODE',
        help=(
            'Choose the scramble mode.\n'
            "Default: 'default'. Choices: 'default', 'ec'."
        ),
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help=(
            'Display statistics of recorded solves.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '--list',
        type=int,
        default=0,
        metavar='SIZE',
        help=(
            'Display the number of last solves.\n'
            'Default: All.'
        ),
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

            if options.solves and solves_done >= options.solves:
                break
        else:
            break

    if not free_play:
        save_solves(puzzle, stack)

    if len(stack) > 1:
        session_stats = Statistics(puzzle, stack)
        session_stats.resume((free_play and 'Session ') or 'Global ')

    return 0
