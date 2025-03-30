import sys
from typing import Any

from term_timer.argparser import ArgumentParser
from term_timer.config import TIMER_CONFIG
from term_timer.constants import CUBE_SIZES


def get_arguments() -> Any:
    countdown = TIMER_CONFIG.get('countdown', 0.0)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

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
        default=countdown,
        metavar='SECONDS',
        help=(
            'Set the countdown timer for inspection time in seconds.\n'
            f'Default: { countdown }.'
        ),
    )
    timer.add_argument(
        '-b', '--metronome',
        type=float,
        default=metronome,
        metavar='TEMPO',
        help=(
            'Set a metronome beep at a specified tempo in seconds.\n'
            f'Default: { metronome }.'
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
        nargs='?',
        type=int,
        const=-1,
        default=False,
        metavar='SOLVES',
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
