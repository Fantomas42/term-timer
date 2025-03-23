import logging
import sys
from random import seed
from typing import Any

from term_timer.argparser import ArgumentParser
from term_timer.console import console
from term_timer.constants import CUBE_SIZES
from term_timer.in_out import load_solves
from term_timer.in_out import save_solves
from term_timer.stats import StatisticsResume
from term_timer.timer import Timer


def get_arguments() -> Any:
    parser = ArgumentParser(
        add_help=False,
        description='Speed cubing timer on your terminal.',
        epilog='Have fun cubing !',
    )
    parser.add_argument(
        'solves',
        nargs='?',
        type=int,
        default=0,
        metavar='SOLVES',
        help=(
            'Specify the number of solves to be done.\n'
            'Default: Infinite.'
        ),
    )

    config = parser.add_argument_group('Configuration')
    config.add_argument(
        '-c', '--cube',
        type=int,
        choices=CUBE_SIZES,
        default=3,
        metavar='CUBE',
        help=(
            'Set the size of the cube (from 2 to 7).\n'
            'Default: 3.'
        ),
    )
    config.add_argument(
        '-p', '--show-cube',
        action='store_true',
        help=(
            'Display the cube in its scrambled state.\n'
            'Default: False.'
        ),
    )
    config.add_argument(
        '-f', '--free-play',
        action='store_true',
        help=(
            'Enable free play mode to disable recording of solves.\n'
            'Default: False.'
        ),
    )

    timer = parser.add_argument_group('Timer')
    timer.add_argument(
        '-i', '--countdown',
        type=int,
        default=0,
        metavar='SECONDS',
        help=(
            'Set the countdown timer for inspection time in seconds.\n'
            'Default: 0.'
        ),
    )
    timer.add_argument(
        '-b', '--metronome',
        type=float,
        default=0,
        metavar='TEMPO',
        help=(
            'Set a metronome beep at a specified tempo in seconds.\n'
            'Default: 0.0.'
        ),
    )

    scramble = parser.add_argument_group('Scramble')
    scramble.add_argument(
        '-e', '--easy-cross',
        action='store_true',
        help=(
            'Set the scramble with an easy cross.\n'
            'Default: False.'
        ),
    )
    scramble.add_argument(
        '-n', '--iterations',
        type=int,
        default=0,
        metavar='ITERATIONS',
        help=(
            'Set the number of random moves.\n'
            'Default: Auto.'
        ),
    )
    scramble.add_argument(
        '-r', '--seed',
        default='',
        metavar='SEED',
        help=(
            'Set a seed for random move generation '
            'to ensure repeatable scrambles.\n'
            'Default: None.'
        ),
    )

    actions = parser.add_argument_group('Actions')
    actions.add_argument(
        '-l', '--list',
        type=int,
        default=0,
        metavar='[SOLVES]',
        help=(
            'Display the last recorded solves.\n'
            'Default: All.'
        ),
    )
    actions.add_argument(
        '-g', '--graph',
        action='store_true',
        help=(
            'Display evolution graph of recorded solves.\n'
            'Default: False.'
        ),
    )
    actions.add_argument(
        '-s', '--stats',
        action='store_true',
        help=(
            'Display statistics of recorded solves.\n'
            'Default: False.'
        ),
    )
    actions.add_argument(
        '-h', '--help',
        action='help',
        help='Display this help message.',
    )

    return parser.parse_args(sys.argv[1:])


def main() -> int:
    options = get_arguments()

    logging.disable(logging.INFO)

    cube = options.cube
    if options.stats or options.list or options.graph:
        session_stats = StatisticsResume(cube, load_solves(cube))

        if options.stats:
            session_stats.resume('Global ')

        if options.list:
            session_stats.listing(options.list)

        if options.graph:
            session_stats.graph()

        return 0

    free_play = options.free_play
    if options.seed or options.iterations or options.easy_cross:
        free_play = True

    if free_play:
        stack = []
        console.print(
            ':lock: Mode Free Play is active, solves will not be recorded !',
            style='warning',
        )
    else:
        stack = load_solves(cube)

    if options.seed:
        seed(options.seed)

    solves_done = 0

    while 42:
        timer = Timer(
            cube_size=cube,
            iterations=options.iterations,
            easy_cross=options.easy_cross,
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
        save_solves(cube, stack)

    if len(stack) > 1:
        session_stats = StatisticsResume(cube, stack)
        session_stats.resume((free_play and 'Session ') or 'Global ')

    return 0
