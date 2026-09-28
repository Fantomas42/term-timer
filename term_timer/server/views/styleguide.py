"""Styleguide view rendering the live design-token catalogue."""
import re
from datetime import date
from datetime import timedelta
from random import Random

from cubing_algs.cases import get_case

from term_timer.constants import STATIC_DIRECTORY
from term_timer.scrambler import scrambler
from term_timer.server.activity import ActivityCalendar
from term_timer.server.annotations import ActivityCalendarData
from term_timer.server.annotations import AttemptsCurve
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import CareerChart
from term_timer.server.annotations import CareerPoint
from term_timer.server.annotations import CaseTile
from term_timer.server.annotations import CaseTrainingTile
from term_timer.server.annotations import ChartPoint
from term_timer.server.annotations import DesignStyleguideContext
from term_timer.server.annotations import DistributionChart
from term_timer.server.annotations import FluencyData
from term_timer.server.annotations import ForecastChart
from term_timer.server.annotations import ForgettingCurve
from term_timer.server.annotations import FormChart
from term_timer.server.annotations import MovesTimingChart
from term_timer.server.annotations import PlayerData
from term_timer.server.annotations import RecognitionData
from term_timer.server.annotations import StepsTpsChart
from term_timer.server.annotations import StyleguideAlgorithm
from term_timer.server.annotations import StyleguideContext
from term_timer.server.annotations import StyleguideGroup
from term_timer.server.annotations import StyleguideSolveRow
from term_timer.server.annotations import StyleguideToken
from term_timer.server.annotations import TrainingStateRow
from term_timer.server.annotations import TrendChart
from term_timer.server.design import DesignTheme
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import algorithm_tokens
from term_timer.server.views.academy import AcademyCaseView
from term_timer.server.views.academy import AcademyView
from term_timer.server.views.base import View
from term_timer.stats import Statistics

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

# Last day of the dated fixtures, and their number of solves.
FIXTURE_DAY = date(2026, 9, 27)
FIXTURE_TIMES = 120
# Solves of a day of the punchcard demo, walked with a stride.
FIXTURE_COUNTS = (0, 0, 0, 1, 2, 0, 3, 5, 0, 9, 17, 1, 0)

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

# Training of the case tiles demo: due and slipping, then slowing down.
FIXTURE_TILES: tuple[CaseTrainingTile, ...] = (
    {'state_label': 'Review', 'state_class': 'review', 'overdue': True,
     'attempts': 18, 'ao5': 2_140_000_000, 'trend': 'flat',
     'speed': 'mid', 'memory': '1', 'retention': 72.4},
    {'state_label': 'Stable', 'state_class': 'stable', 'overdue': False,
     'attempts': 42, 'ao5': 1_380_000_000, 'trend': 'down',
     'speed': 'slow-1', 'memory': '4', 'retention': 97.1},
)


def fixture_state(label: str, count: int, overdue: int) -> TrainingStateRow:
    """
    Build a row of the cards by state demo, over 57 cases.

    Returns:
        The state row.

    """
    return {
        'label': label, 'klass': label.lower(), 'count': count,
        'overdue': overdue, 'share': count * 100 / 57, 'offset': 0.0,
        'best': 0, 'average': 0, 'worst': 0,
    }


FIXTURE_STATES: tuple[TrainingStateRow, ...] = (
    fixture_state('New', 12, 0),
    fixture_state('Learning', 6, 2),
    fixture_state('Relearning', 3, 3),
    fixture_state('Review', 9, 9),
    fixture_state('Stable', 27, 0),
)

FIXTURE_PLAYER: PlayerData = {
    'alg': "R U R' U R U2 R'",
    'setup': '',
    'anchor': 'end',
    'puzzle': '3x3x3',
    'timing': [],
    'index': {},
}

# Power law of the FSRS forgetting curve: recall 90% after the
# stability.
FSRS_DECAY = -0.5
FSRS_FACTOR = 19 / 81

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
            'activity': DesignStyleguideView.activity(),
            'times': DesignStyleguideView.times(),
            'form_chart': DesignStyleguideView.form_chart(),
            'trend_chart': DesignStyleguideView.trend_chart(),
            'distribution_chart': DesignStyleguideView.distribution_chart(),
            'career_chart': DesignStyleguideView.career_chart(),
            'case_tiles': DesignStyleguideView.case_tiles(),
            'state_rows': list(FIXTURE_STATES),
            'player_data': FIXTURE_PLAYER,
            'attempts_chart': DesignStyleguideView.attempts_chart(),
            'forgetting_chart': DesignStyleguideView.forgetting_chart(),
            'forecast_chart': DesignStyleguideView.forecast_chart(),
        }

    @staticmethod
    def activity() -> ActivityCalendarData:
        """
        Lay a year of activity, idle days and busy ones mixed.

        Returns:
            The calendar of the punchcard demo.

        """
        counts = {
            FIXTURE_DAY - timedelta(days=offset): FIXTURE_COUNTS[
                offset * 7 % len(FIXTURE_COUNTS)
            ]
            for offset in range(365)
        }
        return ActivityCalendar(counts).layout(FIXTURE_DAY)

    @staticmethod
    def times() -> list[float | None]:
        """
        Give times slowly getting faster, one DNF among them.

        Returns:
            The times in seconds, None for the DNF.

        """
        times: list[float | None] = [
            round(32 - 6 * index / FIXTURE_TIMES
                  + (index * 37 % 17 - 8) / 2.5, 3)
            for index in range(FIXTURE_TIMES)
        ]
        times[FIXTURE_TIMES // 3] = None
        return times

    @staticmethod
    def averages(size: int) -> list[float | None]:
        """
        Compute the plain mean of the last fixture times at every solve.

        Returns:
            One value per time, None before enough times.

        """
        times = [time or 0.0 for time in DesignStyleguideView.times()]
        return [
            round(sum(times[index + 1 - size:index + 1]) / size, 3)
            if index + 1 >= size else None
            for index in range(len(times))
        ]

    @staticmethod
    def form_chart() -> FormChart:
        """
        Give the last fixture times, their Ao12 and the best of it.

        Returns:
            The data of the form chart.

        """
        ao12 = DesignStyleguideView.averages(12)
        return {
            'points': DesignStyleguideView.times()[-60:],
            'ao12': ao12[-60:],
            'best': min(value for value in ao12 if value),
        }

    @staticmethod
    def trend_chart() -> TrendChart:
        """
        Give the fixture times with three rolling averages.

        Returns:
            The data of the trend chart and its legend.

        """
        times = DesignStyleguideView.times()
        return {
            'indices': [str(index + 1) for index in range(len(times))],
            'times': times,
            'series': [
                {'label': f'Ao{ size }',
                 'data': DesignStyleguideView.averages(size)}
                for size in (5, 12, 50)
            ],
            'ceiling': 40,
            'legend': [
                ('dot', 'Solve'), ('3', 'Ao5'), ('1', 'Ao12'), ('4', 'Ao50'),
            ],
        }

    @staticmethod
    def distribution_chart() -> DistributionChart:
        """
        Count the fixture times per bucket of five seconds.

        Returns:
            The data of the distribution chart and its mode.

        """
        buckets: dict[int, int] = {}
        for time in DesignStyleguideView.times():
            if time:
                bucket = int(time // 5 * 5)
                buckets[bucket] = buckets.get(bucket, 0) + 1
        edges = sorted(buckets)
        mode = max(edges, key=buckets.__getitem__)
        return {
            'labels': [f'{ edge }s' for edge in edges],
            'counts': [buckets[edge] for edge in edges],
            'mode': f'{ mode }s',
        }

    @staticmethod
    def career_chart() -> CareerChart:
        """
        Spread the fixture times over two series and a year.

        Returns:
            The data of the career chart.

        """
        times = DesignStyleguideView.times()
        step = 365 // len(times)
        points: list[CareerPoint] = [
            {'x': index * step, 'y': time,
             'k': 'default' if index < len(times) // 2 else 'daily'}
            for index, time in enumerate(times) if time
        ]
        average = DesignStyleguideView.averages(12)
        return {
            'start': (FIXTURE_DAY - timedelta(days=365)).isoformat(),
            'days': 365,
            'points': points,
            'line': [
                {'x': index * step, 'y': value}
                for index, value in enumerate(average) if value
            ],
            'floor': 15,
            'ceiling': 45,
            'kinds': [
                {'key': 'daily', 'label': 'Daily', 'role': 'chart-1'},
                {'key': 'default', 'label': 'Default', 'role': 'chart-3'},
            ],
            'labels': {'daily': 'Daily', 'default': 'Default'},
        }

    @staticmethod
    def case_tiles() -> list[CaseTile]:
        """
        Case tiles of every kind: trained and due, trained with a
        solution of its own and slowing down, never trained.

        Returns:
            The tiles of the case grid demo.

        """
        academy = AcademyView()
        return [
            academy.build_tile(
                get_case('CFOP/PLL', 'Aa'), FIXTURE_TILES[0],
                note='overdue by 2 d',
            ),
            academy.build_tile(
                get_case('CFOP/OLL', '27'), FIXTURE_TILES[1],
                "R U R' U R U2 R'",
            ),
            academy.build_tile(get_case('CFOP/F2L', '02'), None),
        ]

    @staticmethod
    def attempts_chart() -> AttemptsCurve | None:
        """
        Twenty attempts of a case getting faster.

        Returns:
            The data of the training-attempts chart.

        """
        return AcademyCaseView.build_attempts_curve(
            Statistics.from_milliseconds([
                2600 - index * 45 + (index * 37 % 11 - 5) * 40
                for index in range(20)
            ]),
        )

    @staticmethod
    def forgetting_chart() -> ForgettingCurve:
        """
        Sample the recall of a case of five days of stability with the
        power law of FSRS, reviewed eight days ago and due after six.

        Returns:
            The data of the training-forgetting chart.

        """
        def recall(days: float) -> float:
            return float(100 * (1 + FSRS_FACTOR * days / 5) ** FSRS_DECAY)

        return {
            'points': [
                {'x': days, 'y': recall(days)} for days in range(13)
            ],
            'today': 8.0,
            'due': 6.0,
            'retention': recall(8),
        }

    @staticmethod
    def forecast_chart() -> ForecastChart:
        """
        Reviews of three steps over a week, overdue first.

        Returns:
            The data of the training-forecast chart.

        """
        return {
            'labels': ['Overdue', 'Today', 'Tomorrow', 'Wed 30', 'Thu 01',
                       'Fri 02', 'Sat 03'],
            'series': [
                {'label': 'F2L', 'role': 'chart-1',
                 'data': [3, 1, 0, 2, 0, 1, 0]},
                {'label': 'OLL', 'role': 'chart-3',
                 'data': [5, 2, 4, 0, 1, 3, 0]},
                {'label': 'PLL', 'role': 'chart-4',
                 'data': [1, 0, 1, 0, 0, 2, 1]},
            ],
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
