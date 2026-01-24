"""Command-line argument definitions and parsing for the timer application."""

import sys
from argparse import Namespace
from argparse import _SubParsersAction
from typing import TYPE_CHECKING
from typing import Final

from cubing_algs.constants import ORIENTATIONS

from term_timer.argparser import ArgumentParser
from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import DISPLAY_CONFIG
from term_timer.config import SERVER_CONFIG
from term_timer.config import TIMER_CONFIG
from term_timer.config import TRAINER_STEP
from term_timer.config import USE_GYROSCOPE
from term_timer.constants import CUBE_SIZES

if TYPE_CHECKING:
    _SubParsers = _SubParsersAction[ArgumentParser]

COMMAND_ALIASES: Final[dict[str, list[str]]] = {
    'solve': ['sw', 't'],
    'browse': ['br', 'b'],
    'list': ['ls', 'l'],
    'stats': ['st', 's'],
    'graph': ['gr', 'g'],
    'cfop': ['op', 'c'],
    'detail': ['dt', 'd'],
    'import': ['im', 'i'],
    'serve': ['se', 'h'],
    'train': ['tr', 'w'],
    'edit': ['ed', 'e'],
    'delete': ['rm', 'r'],
    'index': ['ix', 'x'],
    'scramble': ['sc', 'z'],
    'merge': ['mg', 'j'],
    'config': ['cf', 'k'],
}

COMMAND_RESOLUTIONS: dict[str, str] = {}
for name, aliases in COMMAND_ALIASES.items():
    for alias in aliases:
        COMMAND_RESOLUTIONS[alias] = name

ORIENTATIONS_SORTED: Final[list[str]] = sorted(ORIENTATIONS)


def set_session_arguments(
        parser: ArgumentParser,
) -> ArgumentParser._ArgumentGroup:
    """
    Add session-related command-line arguments to parser.

    Returns:
        Argument group containing session-related options.

    """
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


def solve_arguments(subparsers: '_SubParsers') -> ArgumentParser:  # noqa: PLR0914
    """
    Create argument parser for solve command.

    Returns:
        Configured argument parser for solve command.

    """
    countdown = TIMER_CONFIG.get('countdown', 0.0)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

    show_cube = DISPLAY_CONFIG.get('scramble', True)
    show_tps_graph = DISPLAY_CONFIG.get('tps_graph', True)
    show_time_graph = DISPLAY_CONFIG.get('time_graph', True)
    show_fluency_graph = DISPLAY_CONFIG.get('fluency_graph', True)
    show_recognition_graph = DISPLAY_CONFIG.get('recognition_graph', True)
    show_reconstruction = DISPLAY_CONFIG.get('reconstruction', True)
    show_cheers = DISPLAY_CONFIG.get('cheers', True)

    parser = subparsers.add_parser(
        'solve',
        help='Start the timer and record solves',
        description=(
            'Start the speed cubing timer '
            'to record and time your solves.'
        ),
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

    cube = parser.add_argument_group('Cube')
    mode = 'hide' if show_cube else 'show'
    cube.add_argument(
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
    cube.add_argument(
        '-o', '--orientation',
        default='auto',
        choices=['auto', *ORIENTATIONS_SORTED],
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            'Default: auto.'
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
    mode = 'disable' if USE_GYROSCOPE else 'enable'
    bluetooth.add_argument(
        '-g', f'--{ mode }-gyroscope',
        action='store_const',
        const=not USE_GYROSCOPE,
        default=USE_GYROSCOPE,
        dest='use_gyroscope',
        help=(
            f"{ mode.title() } the cube's gyroscope.\n"
            'Default: False'
        ),
    )
    bluetooth.add_argument(
        '-m', '--method',
        default=CUBE_METHOD,
        choices={
            'lbl', 'cfop', 'cf4op', 'raw',
        },
        metavar='METHOD',
        help=(
            'Set the method of analyse used.\n'
            f'Default: { CUBE_METHOD }.'
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
    mode = 'hide' if show_cheers else 'show'
    bluetooth.add_argument(
        '-a', f'--{ mode }-cheers',
        action='store_const',
        const=not show_cheers,
        default=show_cheers,
        dest='show_cheers',
        help=(
            f'{ mode.title() } cheers after analysis.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_time_graph else 'show'
    bluetooth.add_argument(
        '-t', f'--{ mode }-time-graph',
        action='store_const',
        const=not show_time_graph,
        default=show_time_graph,
        dest='show_time_graph',
        help=(
            f'{ mode.title() } the time scatter graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_tps_graph else 'show'
    bluetooth.add_argument(
        '-v', f'--{ mode }-tps-graph',
        action='store_const',
        const=not show_tps_graph,
        default=show_tps_graph,
        dest='show_tps_graph',
        help=(
            f'{ mode.title() } the TPS graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_fluency_graph else 'show'
    bluetooth.add_argument(
        '-z', f'--{ mode }-fluency-graph',
        action='store_const',
        const=not show_fluency_graph,
        default=show_fluency_graph,
        dest='show_fluency_graph',
        help=(
            f'{ mode.title() } the fluency graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_recognition_graph else 'show'
    bluetooth.add_argument(
        '-w', f'--{ mode }-recognition-graph',
        action='store_const',
        const=not show_recognition_graph,
        default=show_recognition_graph,
        dest='show_recognition_graph',
        help=(
            f'{ mode.title() } the recognition graph of the solve.\n'
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
        '-k', '--metronome',
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
    scramble.add_argument(
        '-x', '--scramble',
        default='',
        metavar='SCRAMBLE',
        help=(
            'Set the scramble to use for solving.\n'
            'Default: None.'
        ),
    )
    scramble.add_argument(
        '-l', '--scrambles-file',
        default='',
        metavar='FILE',
        help=(
            'Load scrambles from a file '
            '(one per line or term-timer z format).\n'
            'Default: None.'
        ),
    )

    return parser


def train_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for train command.

    Returns:
        Configured argument parser for train command.

    """
    show_cube = DISPLAY_CONFIG.get('scramble', True)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

    parser = subparsers.add_parser(
        'train',
        help='Start training your OLL/PLL skills',
        description='Start the trainer to improve your skills.',
        aliases=COMMAND_ALIASES['train'],
    )

    parser.add_argument(
        '-s', '--step',
        default=TRAINER_STEP,
        choices={'cross', 'ecross', 'f2l', 'af2l', 'oll', 'pll'},
        metavar='STEP',
        help=(
            'Specify the training mode : '
            'cross, ecross, f2l, af2l, oll or pll.\n'
            f'Default: { TRAINER_STEP }.'
        ),
    )

    cases = parser.add_argument_group('Case Selection')
    cases.add_argument(
        '-c', '--cases',
        nargs='*',
        default=[],
        metavar='CASES',
        dest='case_codes',
        help=(
            'Names of the step cases to solve.\n'
            'Default: All.'
        ),
    )
    cases.add_argument(
        '-d', '--oldest',
        type=int,
        default=0,
        metavar='N',
        help=(
            'Select N cases least recently practiced.\n'
            'Cases never practiced are prioritized.\n'
            'Mutually exclusive with --cases and --slowest.'
        ),
    )
    cases.add_argument(
        '-t', '--slowest',
        type=int,
        default=0,
        metavar='N',
        help=(
            'Select N cases with worst average of 12.\n'
            'Cases with fewer than 12 attempts are prioritized.\n'
            'Mutually exclusive with --cases and --oldest.'
        ),
    )

    parser.add_argument(
        '-v', '--solution',
        action='store_true',
        dest='show_solution',
        help=(
            'Show the main solution of the case.\n'
            'Default: False.'
        ),
    )

    cube = parser.add_argument_group('Cube')
    mode = 'hide' if show_cube else 'show'
    cube.add_argument(
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
    cube.add_argument(
        '-o', '--orientation',
        default=CUBE_ORIENTATION,
        choices=ORIENTATIONS_SORTED,
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            f'Default: { CUBE_ORIENTATION }.'
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
    mode = 'disable' if USE_GYROSCOPE else 'enable'
    bluetooth.add_argument(
        '-g', f'--{ mode }-gyroscope',
        action='store_const',
        const=not USE_GYROSCOPE,
        default=USE_GYROSCOPE,
        dest='use_gyroscope',
        help=(
            f"{ mode.title() } the cube's gyroscope.\n"
            'Default: False'
        ),
    )

    session = parser.add_argument_group('Session')
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
        '-k', '--metronome',
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


def list_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for list command.

    Returns:
        Configured argument parser for list command.

    """
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

    filters = parser.add_argument_group('Filters')
    filters.add_argument(
        '--with-comments',
        action='store_true',
        help='Show only solves with comments.',
    )
    filters.add_argument(
        '--without-comments',
        action='store_true',
        help='Show only solves without comments.',
    )
    filters.add_argument(
        '--connected',
        action='store_true',
        help='Show only solves performed with Bluetooth cube.',
    )
    filters.add_argument(
        '--unconnected',
        action='store_true',
        help='Show only solves performed without Bluetooth cube.',
    )
    filters.add_argument(
        '--dnf',
        action='store_true',
        help='Show only DNF solves.',
    )
    filters.add_argument(
        '--plus-two',
        action='store_true',
        help='Show only +2 penalty solves.',
    )
    filters.add_argument(
        '--no-penalty',
        action='store_true',
        help='Show only solves without penalties.',
    )
    filters.add_argument(
        '--search-comment',
        type=str,
        metavar='TEXT',
        help='Search for text in comments (case-insensitive).',
    )
    filters.add_argument(
        '--search-scramble',
        type=str,
        metavar='TEXT',
        help='Search for text in scrambles (case-insensitive).',
    )
    filters.add_argument(
        '--min-time',
        type=float,
        metavar='SECONDS',
        help='Show only solves with time >= specified value (in seconds).',
    )
    filters.add_argument(
        '--max-time',
        type=float,
        metavar='SECONDS',
        help='Show only solves with time <= specified value (in seconds).',
    )

    set_session_arguments(parser)

    return parser


def browse_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for browse command.

    Returns:
        Configured argument parser for browse command.

    """
    return subparsers.add_parser(
        'browse',
        help='Browse solve sessions interactively',
        description='Interactive TUI for browsing solve sessions and details.',
        aliases=COMMAND_ALIASES['browse'],
    )


def index_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for index command.

    Returns:
        Configured argument parser for index command.

    """
    parser = subparsers.add_parser(
        'index',
        help='List sessions',
        description='Display the list of existing sessions.',
        aliases=COMMAND_ALIASES['index'],
    )

    return parser  # noqa: RET504


def statistics_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for stats command.

    Returns:
        Configured argument parser for stats command.

    """
    parser = subparsers.add_parser(
        'stats',
        help='Display statistics',
        description='Display statistics about recorded solves.',
        aliases=COMMAND_ALIASES['stats'],
    )

    set_session_arguments(parser)

    return parser


def graph_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for graph command.

    Returns:
        Configured argument parser for graph command.

    """
    parser = subparsers.add_parser(
        'graph',
        help='Display trend graph',
        description='Display trend graph for recorded solves.',
        aliases=COMMAND_ALIASES['graph'],
    )

    set_session_arguments(parser)

    return parser


def cfop_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for cfop command.

    Returns:
        Configured argument parser for cfop command.

    """
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


def import_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for import command.

    Returns:
        Configured argument parser for import command.

    """
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


def serve_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for serve command.

    Returns:
        Configured argument parser for serve command.

    """
    domain = SERVER_CONFIG.get('domain', 'localhost')
    port = SERVER_CONFIG.get('port', 8333)

    parser = subparsers.add_parser(
        'serve',
        help='Serve solves in HTML',
        description='Serve HTML reports about recorded solves.',
        aliases=COMMAND_ALIASES['serve'],
    )
    parser.add_argument(
        '--host',
        default=domain,
        help=(
            'Set the hostname of the server.\n'
            f'Default: { domain }.'
        ),
    )
    parser.add_argument(
        '--port',
        type=int,
        default=port,
        help=(
            'Set the port of the server.\n'
            f'Default: { port }.'
        ),
    )

    return parser


def detail_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for detail command.

    Returns:
        Configured argument parser for detail command.

    """
    show_cube = DISPLAY_CONFIG.get('scramble', True)
    show_tps_graph = DISPLAY_CONFIG.get('tps_graph', True)
    show_time_graph = DISPLAY_CONFIG.get('time_graph', True)
    show_fluency_graph = DISPLAY_CONFIG.get('fluency_graph', True)
    show_recognition_graph = DISPLAY_CONFIG.get('recognition_graph', True)
    show_reconstruction = DISPLAY_CONFIG.get('reconstruction', True)
    show_cheers = DISPLAY_CONFIG.get('cheers', True)

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

    cube = parser.add_argument_group('Cube')
    mode = 'hide' if show_cube else 'show'
    cube.add_argument(
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
    cube.add_argument(
        '-o', '--orientation',
        default='auto',
        choices=['auto', *ORIENTATIONS_SORTED],
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            'Default: auto.'
        ),
    )

    analyze = parser.add_argument_group('Analysis')
    analyze.add_argument(
        '-m', '--method',
        default=CUBE_METHOD,
        choices={
            'lbl', 'cfop', 'cf4op', 'raw',
        },
        metavar='METHOD',
        help=(
            'Set the method of analyse used.\n'
            f'Default: { CUBE_METHOD }.'
        ),
    )
    analyze.add_argument(
        '-g', '--disable-rotations',
        action='store_true',
        help=(
            'Disable rotations if present when analysing.\n'
            'Default: False'
        ),
    )
    mode = 'hide' if show_reconstruction else 'show'
    analyze.add_argument(
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
    mode = 'hide' if show_cheers else 'show'
    analyze.add_argument(
        '-a', f'--{ mode }-cheers',
        action='store_const',
        const=not show_cheers,
        default=show_cheers,
        dest='show_cheers',
        help=(
            f'{ mode.title() } cheers after analysis.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_time_graph else 'show'
    analyze.add_argument(
        '-t', f'--{ mode }-time-graph',
        action='store_const',
        const=not show_time_graph,
        default=show_time_graph,
        dest='show_time_graph',
        help=(
            f'{ mode.title() } the time scatter graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_tps_graph else 'show'
    analyze.add_argument(
        '-v', f'--{ mode }-tps-graph',
        action='store_const',
        const=not show_tps_graph,
        default=show_tps_graph,
        dest='show_tps_graph',
        help=(
            f'{ mode.title() } the TPS graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_fluency_graph else 'show'
    analyze.add_argument(
        '-z', f'--{ mode }-fluency-graph',
        action='store_const',
        const=not show_fluency_graph,
        default=show_fluency_graph,
        dest='show_fluency_graph',
        help=(
            f'{ mode.title() } the fluency graph of the solve.\n'
            'Default: False.'
        ),
    )
    mode = 'hide' if show_recognition_graph else 'show'
    analyze.add_argument(
        '-w', f'--{ mode }-recognition-graph',
        action='store_const',
        const=not show_recognition_graph,
        default=show_recognition_graph,
        dest='show_recognition_graph',
        help=(
            f'{ mode.title() } the recognition graph of the solve.\n'
            'Default: False.'
        ),
    )

    set_session_arguments(parser)

    return parser


def scramble_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for scramble command.

    Returns:
        Configured argument parser for scramble command.

    """
    parser = subparsers.add_parser(
        'scramble',
        help='Generate scrambles for chill cubing',
        description=(
            'Generate advanced scrambles for solving '
            'outside term-timer.'
        ),
        aliases=COMMAND_ALIASES['scramble'],
    )

    parser.add_argument(
        'scrambles',
        nargs='?',
        type=int,
        default=5,
        metavar='SCRAMBLES',
        help=(
            'Specify the number of scrambles to generate.\n'
            'Default: 5.'
        ),
    )

    cube = parser.add_argument_group('Cube')
    cube.add_argument(
        '-p', '--show-cube',
        action='store_true',
        help=(
            'Show the cube in its scrambled state.\n'
            'Default: False'
        ),
    )
    cube.add_argument(
        '-l', '--linear',
        action='store_true',
        help=(
            'Show the scrambled cube in linear mode.\n'
            'Default: False'
        ),
    )
    cube.add_argument(
        '-s', '--no-color',
        action='store_true',
        help=(
            'Show the scrambled cube without color.\n'
            'Default: False'
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

    scramble = parser.add_argument_group('Scramble')
    scramble.add_argument(
        '-e', '--easy-cross',
        action='store_true',
        help=(
            'Set the scrambles with an easy cross.\n'
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

    output = parser.add_argument_group('Output')
    output.add_argument(
        '-f', '--format',
        default='terminal',
        choices={'terminal', 'markdown'},
        metavar='FORMAT',
        help=(
            'Set the output format : terminal or markdown\n'
            'Default: terminal.'
        ),
    )

    return parser


def edit_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for edit command.

    Returns:
        Configured argument parser for edit command.

    """
    parser = subparsers.add_parser(
        'edit',
        help="Edit solves' flag or comment",
        description='Edit flag status or comment on specific solves.',
        aliases=COMMAND_ALIASES['edit'],
    )

    parser.add_argument(
        'solves',
        nargs='+',
        type=int,
        metavar='SOLVE_ID',
        help='ID(s) of the solve(s) to edit state for.',
    )

    parser.add_argument(
        '--flag', '-f',
        metavar='FLAG',
        choices={'OK', '+2', 'DNF'},
        help='Flag to set the solve(s) for.',
    )

    parser.add_argument(
        '--comment', '-m',
        type=str,
        metavar='COMMENT',
        help='Comment to set for the solve(s).',
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt.',
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

    return parser


def delete_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for delete command.

    Returns:
        Configured argument parser for delete command.

    """
    parser = subparsers.add_parser(
        'delete',
        help='Delete solves',
        description='Delete specific solves.',
        aliases=COMMAND_ALIASES['delete'],
    )

    parser.add_argument(
        'solve',
        type=int,
        metavar='SOLVE_ID',
        help='ID of the solve to delete.',
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

    return parser


def merge_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for merge command.

    Returns:
        Configured argument parser for merge command.

    """
    parser = subparsers.add_parser(
        'merge',
        help='Merge multiple sessions into one.',
        description=(
            'Merge solves from multiple sessions into a single session, '
            'sorted by date.'
        ),
        aliases=COMMAND_ALIASES['merge'],
    )

    parser.add_argument(
        'sessions',
        nargs='+',
        metavar='SESSION',
        help='Session files to merge.',
    )

    return parser


def config_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for config command.

    Returns:
        Configured argument parser for config command.

    """
    return subparsers.add_parser(
        'config',
        help='Edit configuration settings',
        description='Interactive TUI for editing term-timer configuration.',
        aliases=COMMAND_ALIASES['config'],
    )


def get_arguments() -> Namespace:
    """
    Parse command-line arguments and return parsed namespace.

    Returns:
        Parsed command-line arguments namespace.

    """
    parser = ArgumentParser(
        description='Speed cubing timer on your terminal.',
        epilog='Have fun cubing !',
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
    )

    solve_arguments(subparsers)
    train_arguments(subparsers)
    browse_arguments(subparsers)
    detail_arguments(subparsers)
    edit_arguments(subparsers)
    delete_arguments(subparsers)
    list_arguments(subparsers)
    index_arguments(subparsers)
    statistics_arguments(subparsers)
    graph_arguments(subparsers)
    cfop_arguments(subparsers)
    serve_arguments(subparsers)
    scramble_arguments(subparsers)
    import_arguments(subparsers)
    merge_arguments(subparsers)
    config_arguments(subparsers)

    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    return args
