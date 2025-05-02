import sys
from typing import Any

from term_timer.argparser import ArgumentParser
from term_timer.config import TIMER_CONFIG
from term_timer.constants import CUBE_SIZES


def set_session_arguments(parser):
    session = parser.add_argument_group('Session')
    session.add_argument(
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
    session.add_argument(
        '-u', '--session',
        nargs='*',
        default=[],
        dest='include_sessions',
        metavar='SESSION',
        help=(
            'Names of the session for solves.\n'
            'Default: None.'
        ),
    )
    session.add_argument(
        '-x', '--exclude-session',
        nargs='*',
        default=[],
        dest='exclude_sessions',
        metavar='SESSION',
        help=(
            'Names of the session to exclude for solves.\n'
            'Default: None.'
        ),
    )

    return session


def solve_arguments(subparsers):
    countdown = TIMER_CONFIG.get('countdown', 0.0)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

    parser = subparsers.add_parser(
        'solve',
        help='Start the timer and record solves',
        description='Start the speed cubing timer to record and time your solves.',
        aliases=['t'],
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
        '-b', '--bluetooth',
        action='store_true',
        help=(
            'Use a Bluetooth-connected cube.\n'
            'Default: False.'
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

    session = parser.add_argument_group('Session')
    session.add_argument(
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
    session.add_argument(
        '-u', '--session',
        default='',
        metavar='SESSION',
        help=(
            'Name of the session for solves.\n'
            'Default: None.'
        ),
    )
    session.add_argument(
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
            f'Default: {countdown}.'
        ),
    )
    timer.add_argument(
        '-m', '--metronome',
        type=float,
        default=metronome,
        metavar='TEMPO',
        help=(
            'Set a metronome beep at a specified tempo in seconds.\n'
            f'Default: {metronome}.'
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

    return parser


def list_arguments(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='Display recorded solves',
        description='Display the list of recorded solves.',
        aliases=['l'],
    )

    parser.add_argument(
        'count',
        nargs='?',
        type=int,
        default=0,
        metavar='COUNT',
        help=(
            'Number of solves to display.\n'
            'Default: All solves.'
        ),
    )
    set_session_arguments(parser)

    return parser


def statistics_arguments(subparsers):
    parser = subparsers.add_parser(
        'stats',
        help='Display statistics information',
        description='Display statistics information about recorded solves.',
        aliases=['s'],
    )

    parser.add_argument(
        '-t', '--cfop',
        action='store_true',
        help=(
            'Include CFOP OLL/PLL case information.\n'
            'Default: False.'
        ),
    )

    parser.add_argument(
        '-g', '--graph',
        action='store_true',
        help=(
            'Display evolution graph of recorded solves.\n'
            'Default: False.'
        ),
    )

    set_session_arguments(parser)

    return parser


def detail_arguments(subparsers):
    parser = subparsers.add_parser(
        'detail',
        help='Display detailed information about solves',
        description='Display detailed information about specific solves.',
        aliases=['d'],
    )

    parser.add_argument(
        'solves',
        nargs='+',
        type=int,
        metavar='SOLVE_ID',
        help='ID(s) of the solve(s) to display details for.',
    )

    set_session_arguments(parser)

    return parser


def get_arguments() -> Any:
    parser = ArgumentParser(
        add_help=False,
        description='Speed cubing timer on your terminal.',
        epilog='Have fun cubing !',
    )

    parser.add_argument(
        '-h', '--help',
        action='help',
        help='Show this help message and exit.',
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
    )

    solve_arguments(subparsers)
    list_arguments(subparsers)
    statistics_arguments(subparsers)
    detail_arguments(subparsers)

    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    return args
