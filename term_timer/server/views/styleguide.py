"""Styleguide view rendering the live design-token catalogue."""
import re
from random import Random

from term_timer.constants import STATIC_DIRECTORY
from term_timer.scrambler import scrambler
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import ChartPoint
from term_timer.server.annotations import DesignStyleguideContext
from term_timer.server.annotations import FluencyData
from term_timer.server.annotations import MovesTimingChart
from term_timer.server.annotations import RecognitionData
from term_timer.server.annotations import StepsTpsChart
from term_timer.server.annotations import StyleguideAlgorithm
from term_timer.server.annotations import StyleguideContext
from term_timer.server.annotations import StyleguideGroup
from term_timer.server.annotations import StyleguideSolveRow
from term_timer.server.annotations import StyleguideToken
from term_timer.server.design import DesignTheme
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import algorithm_tokens
from term_timer.server.views.base import View

STYLESHEET = STATIC_DIRECTORY / 'css' / 'style.css'

FIXTURE_SEED = 'styleguide'

FIXTURE_SOLUTION = "y R U R' U' R' F R2 U' R' U' R U R' F' U2"

# Block markup as the reconstruction filters produce it: AUFs, triggers,
# a slice, a rotation, overheads and both kinds of pause.
FIXTURE_RECONSTRUCTION = (
    "[pre-auf]U'[/pre-auf] [sexy-move]R U R' U'[/sexy-move] [pause].[/pause]"
    " [slice]M'[/slice] [rotation_y]y[/rotation_y] [deletion]U[/deletion]"
    " [addition]U2[/addition] [slot-insert]R U' R'[/slot-insert]"
    " [sune]R U R' U R U2 R'[/sune] F [post-auf]U2[/post-auf]"
    " [reco-pause].[/reco-pause]"
)

# Step name, moves, seconds per move and recognition seconds.
FIXTURE_STEPS = (
    ('Cross', 8, 0.28, 0.0),
    ('F2L', 28, 0.3, 1.1),
    ('OLL', 12, 0.2, 0.9),
    ('PLL', 14, 0.18, 1.3),
)

FIXTURE_BREADCRUMB: list[BreadcrumbItem] = [
    {'label': 'Home', 'href': '/'},
    {'label': 'All sessions 3x3x3', 'href': '#component-header'},
    {'label': '#1181', 'href': ''},
]

FIXTURE_SOLVES: tuple[StyleguideSolveRow, ...] = (
    {'number': 1181, 'time': '25.108', 'seconds': 25.108,
     'tps': 3.11, 'grade': 'B+'},
    {'number': 1180, 'time': '21.604', 'seconds': 21.604,
     'tps': 3.61, 'grade': 'A'},
    {'number': 1179, 'time': '1:02.310', 'seconds': 62.31,
     'tps': 1.44, 'grade': 'F'},
    {'number': 1178, 'time': '19.870', 'seconds': 19.87,
     'tps': 3.92, 'grade': 'S'},
    {'number': 1177, 'time': '27.442', 'seconds': 27.442,
     'tps': 2.87, 'grade': 'C'},
)

BANNER_RE = re.compile(r'/\*\s*(.+?)\s*\*/')
TOKEN_RE = re.compile(
    r'^\s*(--[\w-]+)\s*:\s*([^;]+);'
    r'\s*(?:/\*\s*(.*?)\s*\*/)?',
)


def parse_root_groups(css_text: str) -> list[StyleguideGroup]:
    """
    Parse the :root block into titled groups of design tokens.

    Comment banners inside :root become group titles; every following
    custom-property declaration is collected into the current group, with
    any trailing comment kept as the token note.

    Args:
        css_text: Full content of the stylesheet.

    Returns:
        Ordered list of token groups as found in the :root block.

    """
    lines = css_text.splitlines()

    start = next(
        (i for i, line in enumerate(lines) if ':root' in line),
        -1,
    )
    if start < 0:
        return []

    groups: list[StyleguideGroup] = []
    current: StyleguideGroup = {'title': 'Tokens', 'tokens': []}
    depth = 0

    for index in range(start, len(lines)):
        line = lines[index]
        depth += line.count('{') - line.count('}')

        token_match = TOKEN_RE.match(line)
        if token_match:
            token: StyleguideToken = {
                'name': token_match.group(1),
                'value': token_match.group(2).strip(),
                'note': (token_match.group(3) or '').strip(),
            }
            current['tokens'].append(token)
            continue

        banner_match = BANNER_RE.search(line)
        if banner_match:
            title = banner_match.group(1).strip(' ─-')
            if title:
                if current['tokens']:
                    groups.append(current)
                current = {'title': title, 'tokens': []}

        if depth == 0 and index > start:
            break

    if current['tokens']:
        groups.append(current)

    return groups


class StyleguideView(View):
    """View rendering the design-token and component catalogue."""

    template_name = 'styleguide.html'

    @staticmethod
    def get_context() -> StyleguideContext:
        """
        Build context for the styleguide template.

        Returns:
            Dictionary with token groups parsed from the stylesheet.

        """
        css_text = STYLESHEET.read_text(encoding='utf-8')

        return {
            'token_groups': parse_root_groups(css_text),
        }


class DesignStyleguideView(View):
    """View rendering the V2 design system: theme values and contrasts."""

    template_name = 'v2/styleguide.html'

    @staticmethod
    def get_context() -> DesignStyleguideContext:
        """
        Build context for the V2 styleguide template.

        Returns:
            Dictionary with the theme groups and the measured contrasts.

        """
        theme = DesignTheme.load()

        return {
            'token_groups': [
                {
                    'title': group.title,
                    'tokens': [
                        {
                            'name': f'--{ token.name }',
                            'value': token.value,
                            'note': token.note,
                        }
                        for token in group.tokens
                    ],
                }
                for group in theme.groups()
            ],
            'contrast_checks': [
                {
                    'text': check.text,
                    'background': check.background,
                    'level': check.level,
                    'ratio': round(check.ratio, 2),
                    'minimum': check.minimum,
                    'passed': check.passed,
                }
                for check in theme.contrast_checks()
            ],
            'algorithms': DesignStyleguideView.algorithms(),
            'moves_timing': DesignStyleguideView.moves_timing(),
            'steps_tps': DesignStyleguideView.steps_tps(),
            'steps_recognition': DesignStyleguideView.steps_recognition(),
            'steps_fluency': DesignStyleguideView.steps_fluency(),
            'breadcrumb': FIXTURE_BREADCRUMB,
            'solves': list(FIXTURE_SOLVES),
        }

    @staticmethod
    def algorithms() -> list[StyleguideAlgorithm]:
        """
        Algorithm fixtures, seeded: every chip variant and a long one.

        Returns:
            The algorithms to render with the alg macro.

        """
        rng = Random(FIXTURE_SEED)  # noqa: S311
        scramble, _cube = scrambler(3, 0, rng=rng)
        long_scramble, _cube = scrambler(7, 0, rng=rng)

        return [
            {
                'title': 'Scramble · size l, AUFs off',
                'tokens': algorithm_tokens(scramble, aufs=False),
                'size': 'l',
                'copy_label': 'scramble',
                'key': 's',
                'htm': scramble.metrics.htm,
            },
            {
                'title': 'Solution · triggers, rotation and AUF',
                'tokens': algorithm_tokens(FIXTURE_SOLUTION),
                'size': 'm',
                'copy_label': 'solution',
                'key': 'c',
                'htm': None,
            },
            {
                'title': 'Reconstruction · pauses, slice and overheads',
                'tokens': alg_tokens(FIXTURE_RECONSTRUCTION),
                'size': 'm',
                'copy_label': '',
                'key': '',
                'htm': None,
            },
            {
                'title': f'7x7x7 scramble · { len(long_scramble) } moves,'
                         ' size s',
                'tokens': algorithm_tokens(long_scramble, aufs=False),
                'size': 's',
                'copy_label': 'scramble',
                'key': '',
                'htm': long_scramble.metrics.htm,
            },
        ]

    @staticmethod
    def moves_timing() -> MovesTimingChart:
        """
        Cumulative time of each move of a synthetic CFOP solve.

        Returns:
            The data of the moves-timing chart.

        """
        points: list[ChartPoint] = []
        chart: MovesTimingChart = {'points': points, 'steps': []}
        elapsed = 0.0
        for name, moves, pace, recognition in FIXTURE_STEPS:
            chart['steps'].append({'x': len(points), 'label': name})
            elapsed += recognition
            for _move in range(moves):
                elapsed += pace
                points.append({'x': len(points) + 1, 'y': round(elapsed, 3)})

        return chart

    @staticmethod
    def steps_tps() -> StepsTpsChart:
        """
        TPS and eTPS of each step of the synthetic solve.

        Returns:
            The data of the steps-tps chart.

        """
        return {
            'steps': [
                {
                    'label': name,
                    'tps': round(moves / (moves * pace + recognition), 2),
                    'etps': round(1 / pace, 2),
                }
                for name, moves, pace, recognition in FIXTURE_STEPS
            ],
        }

    @staticmethod
    def steps_recognition() -> list[RecognitionData]:
        """
        Recognition and execution of each step of the synthetic solve.

        Returns:
            The steps of the steps-recognition chart.

        """
        return [
            {
                'label': name,
                'recognition': recognition,
                'execution': round(moves * pace, 2),
            }
            for name, moves, pace, recognition in FIXTURE_STEPS
        ]

    @staticmethod
    def steps_fluency() -> list[FluencyData]:
        """
        Fluency of each step of the synthetic solve, slower is less fluent.

        Returns:
            The steps of the steps-fluency chart.

        """
        return [
            {'label': name, 'fluency': round(100 - 100 * pace)}
            for name, _moves, pace, _recognition in FIXTURE_STEPS
        ]
