"""Command-line argument definitions and parsing for the timer application."""
import os
import sys
from argparse import SUPPRESS
from argparse import Namespace
from argparse import _SubParsersAction
from typing import TYPE_CHECKING
from typing import Final

from cubing_algs.constants import ORIENTATIONS

from term_timer.argparser import ArgumentParser
from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import DEVICE_ADDRESS
from term_timer.config import DISPLAY_CONFIG
from term_timer.config import SERVER_CONFIG
from term_timer.config import TIMER_CONFIG
from term_timer.config import TRAINER_STEP
from term_timer.config import USE_GYROSCOPE
from term_timer.constants import CUBE_SIZES
from term_timer.methods import METHOD_ANALYSERS

if TYPE_CHECKING:
    _SubParsers = _SubParsersAction[ArgumentParser]

COMMAND_ALIASES: Final[dict[str, list[str]]] = {
    'ghost': ['gh', 'p'],
    'daily': ['da', 'y'],
    'solve': ['sw', 't'],
    'browse': ['br', 'b'],
    'list': ['ls', 'l'],
    'stats': ['st', 's'],
    'graph': ['gr', 'g'],
    'cfop': ['op', 'c'],
    'detail': ['dt', 'd'],
    'doctor': ['do', 'o'],
    'import': ['im', 'i'],
    'serve': ['se', 'h'],
    'train': ['tr', 'w'],
    'routine': ['ro', 'n'],
    'drill': ['dl', 'dr'],
    'edit': ['ed', 'e'],
    'delete': ['rm', 'r'],
    'index': ['ix', 'x'],
    'scramble': ['sc', 'z'],
    'merge': ['mg', 'j'],
    'config': ['cf', 'k'],
    'reset': ['rs', 'q'],
}

COMMAND_RESOLUTIONS: dict[str, str] = {}
for name, aliases in COMMAND_ALIASES.items():
    for alias in aliases:
        COMMAND_RESOLUTIONS[alias] = name

ORIENTATIONS_SORTED: Final[list[str]] = sorted(ORIENTATIONS)

METHOD_CHOICES: Final[tuple[str, ...]] = tuple(METHOD_ANALYSERS)


def add_toggle_argument(
        group: ArgumentParser._ArgumentGroup,
        short: str,
        name: str,
        description: str,
        *,
        default: bool,
) -> None:
    """
    Add a display toggle whose flag name reflects the current default.

    The long flag is built from the opposite of the configured default,
    so a section displayed by default exposes its hiding flag, and the
    destination is always the matching `show_*` attribute.
    """
    mode = 'hide' if default else 'show'
    group.add_argument(
        short, f'--{ mode }-{ name }',
        action='store_const',
        const=not default,
        default=default,
        dest=f'show_{ name.replace("-", "_") }',
        help=(
            f'{ mode.title() } { description }.\n'
            'Default: False.'
        ),
    )


def add_method_argument(group: ArgumentParser._ArgumentGroup) -> None:
    """Add the solving method selection argument to group."""
    group.add_argument(
        '-m', '--method',
        default=CUBE_METHOD,
        choices=METHOD_CHOICES,
        metavar='METHOD',
        help=(
            'Set the method of analyse used.\n'
            f'Default: { CUBE_METHOD }.'
        ),
    )


def add_seed_argument(group: ArgumentParser._ArgumentGroup) -> None:
    """Add the random generation seed argument to group."""
    group.add_argument(
        '-r', '--seed',
        default='',
        metavar='SEED',
        help=(
            'Set a seed for random move generation '
            'to ensure repeatable scrambles.\n'
            'Default: None.'
        ),
    )


def add_free_play_argument(
        group: ArgumentParser._ArgumentGroup,
        *,
        description: str = 'disable recording of solves',
) -> None:
    """Add the free play mode argument to group."""
    group.add_argument(
        '-f', '--free-play',
        action='store_true',
        help=(
            f'Enable free play mode to { description }.\n'
            'Default: False.'
        ),
    )


def add_cube_size_argument(group: ArgumentParser._ArgumentGroup) -> None:
    """Add the cube size argument to group."""
    group.add_argument(
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


def set_session_arguments(
        parser: ArgumentParser,
) -> ArgumentParser._ArgumentGroup:
    """
    Add session-related command-line arguments to parser.

    Returns:
        Argument group containing session-related options.

    """
    session = parser.add_argument_group('Session')
    add_cube_size_argument(session)
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


def set_cube_arguments(
        parser: ArgumentParser,
        *,
        orientation_default: str = 'auto',
        orientation_auto: bool = True,
        cube_toggle: bool = True,
) -> ArgumentParser._ArgumentGroup:
    """
    Add cube display and orientation arguments to parser.

    Returns:
        Argument group containing cube-related options.

    """
    show_cube = DISPLAY_CONFIG.get('scramble', True)

    orientations = ORIENTATIONS_SORTED
    if orientation_auto:
        orientations = ['auto', *ORIENTATIONS_SORTED]

    cube = parser.add_argument_group('Cube')
    if cube_toggle:
        add_toggle_argument(
            cube, '-p', 'cube',
            'the cube in its scrambled state',
            default=show_cube,
        )
    cube.add_argument(
        '-o', '--orientation',
        default=orientation_default,
        choices=orientations,
        metavar='ORIENTATION',
        help=(
            'Set the cube orientation used.\n'
            f'Default: { orientation_default }.'
        ),
    )

    return cube


def set_bluetooth_arguments(
        parser: ArgumentParser,
) -> ArgumentParser._ArgumentGroup:
    """
    Add Bluetooth connection arguments to parser.

    Returns:
        Argument group containing Bluetooth connection options.

    """
    use_bluetooth = bool(DEVICE_ADDRESS)

    bluetooth = parser.add_argument_group('Bluetooth')
    mode = 'disable' if use_bluetooth else 'enable'
    bluetooth.add_argument(
        '-b', f'--{ mode }-bluetooth',
        action='store_const',
        const=not use_bluetooth,
        default=use_bluetooth,
        dest='bluetooth',
        help=(
            f'{ mode.title() } the Bluetooth-connected cube.\n'
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
            'Default: False.'
        ),
    )

    return bluetooth


def set_replay_arguments(
        parser: ArgumentParser,
) -> ArgumentParser._ArgumentGroup:
    """
    Add the hidden Bluetooth replay argument to parser.

    Returns:
        Argument group containing replay options.

    """
    replay = parser.add_argument_group('Replay')
    replay.add_argument(
        '--replay',
        default=os.getenv('TERM_TIMER_REPLAY', ''),
        metavar='FILE',
        help=SUPPRESS,
    )

    return replay


def set_analysis_arguments(
        parser: ArgumentParser,
        *,
        steps: bool = True,
        rotations: bool = False,
        doctor_description: str = 'doctor main diagnostic after analysis',
) -> ArgumentParser._ArgumentGroup:
    """
    Add solve analysis and reporting arguments to parser.

    Returns:
        Argument group containing analysis-related options.

    """
    show_steps = TIMER_CONFIG.get('steps', True)
    show_reconstruction = DISPLAY_CONFIG.get('reconstruction', True)
    show_highlights = DISPLAY_CONFIG.get('highlights', True)
    show_doctor = DISPLAY_CONFIG.get('doctor', True)
    show_time_graph = DISPLAY_CONFIG.get('time_graph', True)
    show_tps_graph = DISPLAY_CONFIG.get('tps_graph', True)
    show_fluency_graph = DISPLAY_CONFIG.get('fluency_graph', True)
    show_recognition_graph = DISPLAY_CONFIG.get('recognition_graph', True)

    analysis = parser.add_argument_group('Analysis')
    add_method_argument(analysis)
    if rotations:
        analysis.add_argument(
            '-g', '--disable-rotations',
            action='store_true',
            help=(
                'Disable rotations if present when analysing.\n'
                'Default: False'
            ),
        )
    if steps:
        add_toggle_argument(
            analysis, '-j', 'steps',
            'completed steps during the solve',
            default=show_steps,
        )
    add_toggle_argument(
        analysis, '-s', 'reconstruction',
        'the reconstruction of the solve',
        default=show_reconstruction,
    )
    add_toggle_argument(
        analysis, '-a', 'highlights',
        'highlights after analysis',
        default=show_highlights,
    )
    add_toggle_argument(
        analysis, '-e', 'doctor',
        doctor_description,
        default=show_doctor,
    )
    add_toggle_argument(
        analysis, '-t', 'time-graph',
        'the time scatter graph of the solve',
        default=show_time_graph,
    )
    add_toggle_argument(
        analysis, '-v', 'tps-graph',
        'the TPS graph of the solve',
        default=show_tps_graph,
    )
    add_toggle_argument(
        analysis, '-z', 'fluency-graph',
        'the fluency graph of the solve',
        default=show_fluency_graph,
    )
    add_toggle_argument(
        analysis, '-w', 'recognition-graph',
        'the recognition graph of the solve',
        default=show_recognition_graph,
    )

    return analysis


def set_timer_arguments(
        parser: ArgumentParser,
        *,
        countdown_description: str = (
            'Set the countdown timer for inspection time in seconds.'
        ),
        countdown_argument: bool = True,
) -> ArgumentParser._ArgumentGroup:
    """
    Add countdown and metronome arguments to parser.

    Returns:
        Argument group containing timer-related options.

    """
    countdown = TIMER_CONFIG.get('countdown', 0.0)
    metronome = TIMER_CONFIG.get('metronome', 0.0)

    timer = parser.add_argument_group('Timer')
    if countdown_argument:
        timer.add_argument(
            '-i', '--countdown',
            type=int,
            default=countdown,
            metavar='SECONDS',
            help=(
                f'{ countdown_description }\n'
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

    return timer


def set_scramble_arguments(
        parser: ArgumentParser,
        *,
        plural: bool = False,
) -> ArgumentParser._ArgumentGroup:
    """
    Add scramble generation arguments to parser.

    Returns:
        Argument group containing scramble-related options.

    """
    target = 'scrambles' if plural else 'scramble'

    scramble = parser.add_argument_group('Scramble')
    scramble.add_argument(
        '-ec', '--easy-cross',
        action='store_true',
        help=(
            f'Set the { target } with an easy cross.\n'
            'Default: False.'
        ),
    )
    scramble.add_argument(
        '-eo', '--edges-oriented',
        action='store_true',
        help=(
            f'Set the { target } with edges oriented.\n'
            'Default: False.'
        ),
    )
    scramble.add_argument(
        '-xc', '--x-cross',
        action='store_true',
        help=(
            f'Set the { target } with a x-cross.\n'
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
    add_seed_argument(scramble)

    return scramble


def ghost_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for ghost command.

    Returns:
        Configured argument parser for ghost command.

    """
    parser = subparsers.add_parser(
        'ghost',
        help='Race a recorded solve on the same scramble',
        description=(
            'Race a live solve against a recorded ghost on the same '
            'scramble, seeded from an already-recorded reference solve. '
            'The ghost to beat is the fastest attempt on that scramble.'
        ),
        aliases=COMMAND_ALIASES['ghost'],
    )

    parser.add_argument(
        'solve_id',
        nargs='?',
        type=int,
        default=0,
        metavar='SOLVE_ID',
        help=(
            'ID of the reference solve whose scramble seeds the race.\n'
            'Required to race or to review; omit only with --summary.'
        ),
    )

    set_cube_arguments(parser)

    set_bluetooth_arguments(parser)
    set_replay_arguments(parser)
    set_analysis_arguments(parser)

    session = set_session_arguments(parser)
    add_free_play_argument(
        session,
        description=(
            'race the ghost without recording the attempt '
            'into the scramble file'
        ),
    )

    set_timer_arguments(parser)

    ghost = parser.add_argument_group('Ghost')
    ghost.add_argument(
        '-r', '--review',
        action='store_true',
        help=(
            "Review the stats of the reference solve's scramble file.\n"
            'Default: False.'
        ),
    )
    ghost.add_argument(
        '-l', '--summary',
        action='store_true',
        help=(
            'Browse the ghost library across every recorded scramble.\n'
            'Default: False.'
        ),
    )
    ghost.add_argument(
        '--ghost-3d',
        action='store_true',
        help=(
            'Reserved: parallel OpenGL replay of the ghost cube.\n'
            'Not implemented in v1.'
        ),
    )

    return parser


def daily_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for daily command.

    Returns:
        Configured argument parser for daily command.

    """
    parser = subparsers.add_parser(
        'daily',
        help='Practice the scramble of the day',
        description=(
            "Run the daily scramble: a fixed scramble based on today's date. "
            'Repeat it as many times as needed until satisfied.'
        ),
        aliases=COMMAND_ALIASES['daily'],
    )

    set_cube_arguments(parser)

    set_bluetooth_arguments(parser)
    set_replay_arguments(parser)
    set_analysis_arguments(parser)

    session = parser.add_argument_group('Session')
    add_cube_size_argument(session)
    add_free_play_argument(session)

    set_timer_arguments(parser)

    date = parser.add_argument_group('Date')
    date.add_argument(
        '-d', '--date',
        default='',
        metavar='DATE',
        help=(
            'Set the date for the daily scramble (YYYY-MM-DD).\n'
            'Default: today.'
        ),
    )
    date.add_argument(
        '-r', '--review',
        action='store_true',
        help=(
            'Review the stats of the daily session for the given date.\n'
            'Default: False.'
        ),
    )
    date.add_argument(
        '-l', '--summary',
        action='store_true',
        help=(
            'Show a summary of all daily solves across every session.\n'
            'Default: False.'
        ),
    )

    return parser


def solve_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for solve command.

    Returns:
        Configured argument parser for solve command.

    """
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

    set_cube_arguments(parser)

    set_bluetooth_arguments(parser)
    set_replay_arguments(parser)
    set_analysis_arguments(parser)

    session = parser.add_argument_group('Session')
    add_cube_size_argument(session)
    session.add_argument(
        '-u', '--session',
        default='',
        metavar='SESSION',
        help=(
            'Name of the session for solves.\n'
            'Default: None.'
        ),
    )
    add_free_play_argument(session)

    set_timer_arguments(parser)

    scramble = set_scramble_arguments(parser)
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
    parser = subparsers.add_parser(
        'train',
        help='Start training your OLL/PLL skills',
        description='Start the trainer to improve your skills.',
        aliases=COMMAND_ALIASES['train'],
    )

    parser.add_argument(
        'trainings',
        nargs='?',
        type=int,
        default=0,
        metavar='TRAININGS',
        help=(
            'Specify the number of trainings to be done.\n'
            'Default: Infinite.'
        ),
    )

    parser.add_argument(
        '-s', '--step',
        default=TRAINER_STEP,
        choices={
            'cross', 'ecross', 'xcross',
            'f2l', 'af2l',
            'oll', 'pll', 'll',
        },
        metavar='STEP',
        help=(
            'Specify the training mode : '
            'cross, ecross, xcross, f2l, af2l, oll, ll or ll.\n'
            f'Default: { TRAINER_STEP }.'
        ),
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        dest='list_cases',
        help=(
            'List all available cases with their training statistics.\n'
            'Default: False.'
        ),
    )
    parser.add_argument(
        '-v', '--solution',
        action='store_true',
        dest='show_solution',
        help=(
            'Always show the main solution of the case if exists.\n'
            'Without this flag, the solution is still shown when the '
            'FSRS card\nof the case is in Learning or Relearning state.\n'
            'Default: False.'
        ),
    )
    cases = parser.add_argument_group(
        'Case Selection',
        'By default, cases are selected by FSRS.\n'
        '--oldest, --slowest and --filter restrict the pool while keeping '
        'FSRS active;\n--cases and --random disable FSRS selection '
        '(cards are still updated).',
    )
    cases.add_argument(
        '-m', '--new-cases',
        type=int,
        default=5,
        metavar='N',
        dest='new_cases',
        help=(
            'Maximum new cases to introduce per session.\n'
            'Only applies when FSRS is active.\n'
            'Default: 5.'
        ),
    )
    cases.add_argument(
        '-i', '--filter',
        nargs='+',
        default=[],
        metavar='FILTER',
        dest='filters',
        help=(
            'Filter cases by family or group (e.g. Dot, Cross, OCLL).\n'
            'Multiple values are combined with OR logic.\n'
            'Restricts the case pool; compatible with --oldest, --slowest'
            ' and --random.\n'
            'Incompatible with --cases.'
        ),
    )

    selection = cases.add_mutually_exclusive_group()
    selection.add_argument(
        '-c', '--cases',
        nargs='*',
        default=[],
        metavar='CASES',
        dest='case_codes',
        help=(
            'Practice specific cases by name.\n'
            'Disables FSRS case selection (cards are still updated).\n'
            'Incompatible with --filter, --oldest, --slowest and --random.'
        ),
    )
    selection.add_argument(
        '-d', '--oldest',
        nargs='?',
        type=int,
        default=0,
        const=5,
        metavar='N',
        help=(
            'Select N cases least recently practiced.\n'
            'Cases never practiced are prioritized.\n'
            'Restricts FSRS scheduling to the N oldest cases.\n'
            'Default N: 5.'
        ),
    )
    selection.add_argument(
        '-t', '--slowest',
        nargs='?',
        type=int,
        default=0,
        const=5,
        metavar='N',
        help=(
            'Select N cases with worst average of 12.\n'
            'Cases with fewer than 12 attempts are prioritized.\n'
            'Restricts FSRS scheduling to the N slowest cases.\n'
            'Default N: 5.'
        ),
    )
    selection.add_argument(
        '-n', '--random',
        nargs='?',
        type=int,
        default=0,
        const=-1,
        metavar='N',
        dest='random',
        help=(
            'Select N cases randomly.\n'
            'If N is omitted, all valid cases are used in random order.\n'
            'Disables FSRS case selection (cards are still updated).'
        ),
    )

    set_cube_arguments(
        parser,
        orientation_default=CUBE_ORIENTATION,
        orientation_auto=False,
    )

    set_bluetooth_arguments(parser)

    session = parser.add_argument_group('Session')
    add_free_play_argument(
        session,
        description='disable saving and FSRS scheduling',
    )

    set_timer_arguments(parser, countdown_argument=False)

    scramble = parser.add_argument_group('Scramble')
    add_seed_argument(scramble)

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
            'case', 'count', 'frequency',
            'recognition', 'execution', 'time',
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


def doctor_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for doctor command.

    Returns:
        Configured argument parser for doctor command.

    """
    parser = subparsers.add_parser(
        'doctor',
        help='Display aggregated diagnostics',
        description=(
            'Aggregate doctor diagnostics over the last connected '
            'solves to highlight structural weaknesses.'
        ),
        aliases=COMMAND_ALIASES['doctor'],
    )

    analysis = parser.add_argument_group('Analysis')
    analysis.add_argument(
        '-n', '--count',
        type=int,
        default=50,
        metavar='COUNT',
        help=(
            'Number of last connected solves to diagnose.\n'
            'Default: 50.'
        ),
    )
    add_method_argument(analysis)
    analysis.add_argument(
        '-t', '--trend',
        action='store_true',
        help=(
            'Compare against the previous window of solves.\n'
            'Default: False.'
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

    set_cube_arguments(parser)

    set_analysis_arguments(
        parser,
        steps=False,
        rotations=True,
        doctor_description='doctor diagnostics after analysis',
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
    add_cube_size_argument(session)

    set_scramble_arguments(parser, plural=True)

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
    add_cube_size_argument(session)
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
    add_cube_size_argument(session)
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


def drill_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for drill command.

    Returns:
        Configured argument parser for drill command.

    """
    parser = subparsers.add_parser(
        'drill',
        help='Drill an algorithm repeatedly',
        description=(
            'Time repeated executions of an algorithm '
            'without recording solves.'
        ),
        aliases=COMMAND_ALIASES['drill'],
    )

    parser.add_argument(
        'algorithm',
        type=str,
        metavar='ALGORITHM',
        help=(
            "The algorithm to drill (e.g. \"R U R' U'\").\n"
        ),
    )

    parser.add_argument(
        '-t', '--times',
        type=int,
        default=0,
        metavar='TIMES',
        help=(
            'Number of reps to drill.\n'
            'Default: Infinite.'
        ),
    )

    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=0,
        metavar='SECONDS',
        help=(
            'Stop drilling after this many seconds.\n'
            'Default: Infinite.'
        ),
    )

    set_cube_arguments(
        parser,
        orientation_default=CUBE_ORIENTATION,
        orientation_auto=False,
        cube_toggle=False,
    )

    set_bluetooth_arguments(parser)

    set_timer_arguments(
        parser,
        countdown_description='Set a countdown before each rep.',
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


def routine_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for routine command.

    Returns:
        Configured argument parser for routine command.

    """
    parser = subparsers.add_parser(
        'routine',
        help='Run a daily practice routine from a config file',
        description=(
            'Run a sequence of training and solve sessions '
            'defined in a JSON config file.'
        ),
        aliases=COMMAND_ALIASES['routine'],
    )

    parser.add_argument(
        'routine_file',
        nargs='?',
        type=str,
        default='',
        metavar='FILE',
        help=(
            'Path to the routine JSON config file.\n'
            'Default: List available routines.'
        ),
    )

    return parser


def reset_arguments(subparsers: '_SubParsers') -> ArgumentParser:
    """
    Create argument parser for reset command.

    Returns:
        Configured argument parser for reset command.

    """
    parser = subparsers.add_parser(
        'reset',
        help='Reset the state of the Bluetooth cube',
        description='Connect to a Bluetooth cube and send a reset command.',
        aliases=COMMAND_ALIASES['reset'],
    )

    parser.add_argument(
        '-f', '--filter-name',
        type=str,
        metavar='FILTER',
        default='',
        help='Filter device name to connect to.',
    )

    return parser


def get_parser() -> ArgumentParser:
    """
    Build and return the argument parser without parsing.

    Returns:
        Configured argument parser for term-timer.

    """
    parser = ArgumentParser(
        prog='term-timer',
        description='Speed cubing timer on your terminal.',
        epilog='Have fun cubing !',
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
    )

    ghost_arguments(subparsers)
    daily_arguments(subparsers)
    solve_arguments(subparsers)
    train_arguments(subparsers)
    drill_arguments(subparsers)
    routine_arguments(subparsers)
    reset_arguments(subparsers)
    browse_arguments(subparsers)
    detail_arguments(subparsers)
    edit_arguments(subparsers)
    delete_arguments(subparsers)
    list_arguments(subparsers)
    index_arguments(subparsers)
    statistics_arguments(subparsers)
    graph_arguments(subparsers)
    cfop_arguments(subparsers)
    doctor_arguments(subparsers)
    serve_arguments(subparsers)
    scramble_arguments(subparsers)
    import_arguments(subparsers)
    merge_arguments(subparsers)
    config_arguments(subparsers)

    return parser


def get_arguments() -> Namespace:
    """
    Parse command-line arguments and return parsed namespace.

    Returns:
        Parsed command-line arguments namespace.

    """
    parser = get_parser()
    args = parser.parse_args(sys.argv[1:])

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    return args
