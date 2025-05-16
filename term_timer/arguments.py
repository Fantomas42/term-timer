import sys
from typing import Any

from term_timer.argparser import ArgumentParser
from term_timer.config import CUBE_METHOD
from term_timer.config import DISPLAY_CONFIG
from term_timer.config import TIMER_CONFIG
from term_timer.constants import CUBE_SIZES

COMMAND_ALIASES = {
    'solve': ['sw', 't'],
    'list': ['ls', 'l'],
    'stats': ['st', 's'],
    'graph': ['gr', 'g'],
    'cfop': ['op', 'c'],
    'detail': ['dt', 'd'],
    'import': ['im', 'i'],
    'serve': ['se', 'h'],
}

COMMAND_RESOLUTIONS = {}
for name, aliases in COMMAND_ALIASES.items():
    for alias in aliases:
        COMMAND_RESOLUTIONS[alias] = name


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
        '-u', '--include-sessions',
        nargs='*',
        default=[],
        metavar='SESSION',
        help=(
            'Names of the session for solves.\n'
            'Default: None.'
        ),
    )
    session.add_argument(
        '-x', '--exclude-sessions',
        nargs='*',
        default=[],
        metavar='SESSION',
        help=(
            'Names of the session to exclude for solves.\n'
            'Default: None.'
        ),
    )
    session.add_argument(
        '-d', '--devices',
        nargs='*',
        default=[],
        metavar='DEVICE',
        help=(
            'Filter solves by device names.\n'
            'Default: None.'
        ),
    )

    return session


def solve_arguments(subparsers):
    countdown = TIMER_CONFIG.get('countdown', 0.0)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

    show_cube = DISPLAY_CONFIG.get('scramble', True)
    show_timegraph = DISPLAY_CONFIG.get('timegraph', True)
    show_reconstruction = DISPLAY_CONFIG.get('reconstruction', True)

    parser = subparsers.add_parser(
        'solve',
        help='Start the timer and record solves',
        description='Start the speed cubing timer to record and time your solves.',
        aliases=COMMAND_ALIASES['solve'],
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

    mode = 'hide' if show_cube else 'show'
    parser.add_argument(
        '-p', f'--{ mode }-cube',
        action='store_const',
        const=not show_cube,
        default=show_cube,
        dest='show_cube',
        help=(
            f'{ mode.title() } the cube in its scrambled state.\n'
            'Default: False'
        ),
    )

    bluetooth = parser.add_argument_group('Bluetooth')
    bluetooth.add_argument(
        '-b', '--bluetooth',
        action='store_true',
        help=(
            'Use a Bluetooth-connected cube.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_reconstruction else 'show'
    bluetooth.add_argument(
        '-s', f'--{ mode }-reconstruction',
        action='store_const',
        const=not show_reconstruction,
        default=show_reconstruction,
        dest='show_reconstruction',
        help=(
            f'{ mode.title() } the reconstruction of the solve.\n'
            'Default: False'
        ),
    )
    mode = 'hide' if show_timegraph else 'show'
    bluetooth.add_argument(
        '-g', f'--{ mode }-time-graph',
        action='store_const',
        const=not show_timegraph,
        default=show_timegraph,
        dest='show_time_graph',
        help=(
            f'{ mode.title() } the time scatter graph of the solve.\n'
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
            f'Default: { countdown }.'
        ),
    )
    timer.add_argument(
        '-m', '--metronome',
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

    return parser


def list_arguments(subparsers):
    parser = subparsers.add_parser(
        'list',
        help='Display recorded solves',
        description='Display the list of recorded solves.',
        aliases=COMMAND_ALIASES['list'],
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

    sort = parser.add_argument_group('Sorting')
    sort.add_argument(
        '-s', '--sort',
        default='date',
        choices={'date', 'time'},
        metavar='SORT',
        help=(
            'Set the sorting attribute of the solves.\n'
            'Default: date.'
        ),
    )

    set_session_arguments(parser)

    return parser


def statistics_arguments(subparsers):
    parser = subparsers.add_parser(
        'stats',
        help='Display statistics',
        description='Display statistics about recorded solves.',
        aliases=COMMAND_ALIASES['stats'],
    )

    set_session_arguments(parser)

    return parser


def graph_arguments(subparsers):
    parser = subparsers.add_parser(
        'graph',
        help='Display trend graph',
        description='Display trend graph for recorded solves.',
        aliases=COMMAND_ALIASES['graph'],
    )

    set_session_arguments(parser)

    return parser


def cfop_arguments(subparsers):
    parser = subparsers.add_parser(
        'cfop',
        help='Display CFOP cases',
        description='Display CFOP OLL and PLL information for recorded solves.',
        aliases=COMMAND_ALIASES['cfop'],
    )

    cases = parser.add_argument_group('Cases')
    cases.add_argument(
        '--oll',
        action='store_true',
        help=(
            'Display only OLL cases.\n'
            'Default: False.'
        ),
    )
    cases.add_argument(
        '--pll',
        action='store_true',
        help=(
            'Display only OLL cases.\n'
            'Default: False.'
        ),
    )

    sort = parser.add_argument_group('Sorting')
    sort.add_argument(
        '-s', '--sort',
        default='count',
        choices={
            'case', 'count', 'frequency', 'probability',
            'inspection', 'execution', 'time',
            'ao5', 'ao12', 'qtm', 'tps', 'etps',
        },
        metavar='SORT',
        help=(
            'Set the sorting attribute of the cases.\n'
            'Default: count.'
        ),
    )
    sort.add_argument(
        '-o', '--order',
        default='asc',
        choices={'asc', 'desc'},
        metavar='ORDER',
        help=(
            'Set the ordering attribute of the cases.\n'
            'Default: asc.'
        ),
    )

    set_session_arguments(parser)

    return parser


def import_arguments(subparsers):
    parser = subparsers.add_parser(
        'import',
        help='Import external solves',
        description='Import solves recorded in csTimer or Cubeast.',
        aliases=COMMAND_ALIASES['import'],
    )
    parser.add_argument(
        'source',
        help='Solve file to import',
    )

    return parser


def serve_arguments(subparsers):
    parser = subparsers.add_parser(
        'serve',
        help='Serve solves in HTML',
        description='Serve HTML reports about recorded solves.',
        aliases=COMMAND_ALIASES['serve'],
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help=(
            'Set the hostname of the server.\n'
            'Default: localhost.'
        ),
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help=(
            'Set the port of the server.\n'
            'Default: 8080.'
        ),
    )

    return parser


def detail_arguments(subparsers):
    parser = subparsers.add_parser(
        'detail',
        help='Display detailed information about solves',
        description='Display detailed information about specific solves.',
        aliases=COMMAND_ALIASES['detail'],
    )

    parser.add_argument(
        'solves',
        nargs='+',
        type=int,
        metavar='SOLVE_ID',
        help='ID(s) of the solve(s) to display details for.',
    )
    analyze = parser.add_argument_group('Analysis')
    analyze.add_argument(
        '-m', '--method',
        default=CUBE_METHOD,
        choices={
            'lbl', 'cfop', 'cf4op',
        },
        metavar='METHOD',
        help=(
            'Set the method of analyse used.\n'
            f'Default: { CUBE_METHOD }.'
        ),
    )

    set_session_arguments(parser)

    return parser


def get_arguments() -> Any:
    parser = ArgumentParser(
        description='Speed cubing timer on your terminal.',
        epilog='Have fun cubing !',
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
    )

    solve_arguments(subparsers)
    list_arguments(subparsers)
    statistics_arguments(subparsers)
    graph_arguments(subparsers)
    cfop_arguments(subparsers)
    detail_arguments(subparsers)
    import_arguments(subparsers)
    serve_arguments(subparsers)

    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    return args
