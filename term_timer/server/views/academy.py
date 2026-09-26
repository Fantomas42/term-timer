"""Academy overview, step, and case views."""
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from hashlib import sha1
from math import ceil
from typing import TYPE_CHECKING
from typing import ClassVar
from typing import cast

from bottle import abort
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

if TYPE_CHECKING:
    from cubing_algs.cases.case import Case
from cubing_algs.display.palettes import PALETTES

from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.constants import CUBE_SIZES
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.formatter import format_relative_delay
from term_timer.formatter import fsrs_state_label
from term_timer.fsrs.scheduler import FSRSScheduler
from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.fsrs.storage import TrainingStateSummary
from term_timer.in_out import read_trainings
from term_timer.in_out import trainings_path
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import AcademyCaseAlgorithmsDebugContext
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AlgorithmImpactGroup
from term_timer.server.annotations import AttemptsCurve
from term_timer.server.annotations import CaseTrainingPanel
from term_timer.server.annotations import CaseTrainingTile
from term_timer.server.annotations import CurvePoint
from term_timer.server.annotations import ForgettingCurve
from term_timer.server.annotations import MethodInfo
from term_timer.server.annotations import StepTrainingSummary
from term_timer.server.annotations import TrainingReviewContext
from term_timer.server.annotations import TrainingStateRow
from term_timer.server.modes import get_mode_groups
from term_timer.server.views.base import View
from term_timer.stats import Statistics

# How far past the later of today and the due date the forgetting curve
# is drawn, as a share of the elapsed span.
FORGETTING_MARGIN = 0.5

DAY_SECONDS = 86400

# Speed tint of the step grid: Ao5 of a case over the median Ao5 of the
# step, from the fastest band to the slowest; ratios between the two
# inner bounds are the middle. Below SPEED_MIN_CASES timed cases the
# median means nothing and no case is tinted.
SPEED_MIN_CASES = 5
SPEED_BANDS: tuple[tuple[float, str], ...] = (
    (0.80, 'fast-2'),
    (0.93, 'fast-1'),
    (1.07, 'mid'),
    (1.25, 'slow-1'),
)
SPEED_SLOWEST = 'slow-2'

# Memory tint of the step grid: current recall probability in percent,
# lowest bound of each level from the strongest down.
MEMORY_LEVELS: tuple[tuple[float, str], ...] = (
    (95.0, '4'),
    (90.0, '3'),
    (80.0, '2'),
    (60.0, '1'),
)
MEMORY_WEAKEST = '0'


class AcademyView(View):
    """View for displaying academy overview with solving methods."""

    template_name = 'academy/overview.html'
    orientation: CubeOrientation = ''
    display_mode: str = ''
    cube_size: int = 3
    palette: str = ''
    methods: ClassVar[dict[str, MethodInfo]] = {
        'CFOP': {
            'cube_size': 3,
            'description': (
                'Cross, F2L, OLL, PLL - The most popular speedcubing method'
            ),
            'steps': {
                'F2L': {
                    'description': (
                        'First Two Layers - '
                        'Solve cross and first two layers simultaneously'
                    ),
                    'mode': 'f2l',
                },
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'mode': 'oll',
                },
                'PLL': {
                    'description': (
                        'Permutation of Last Layer - '
                        'Permute all pieces on the last layer'
                    ),
                    'mode': 'pll',
                },
                'AF2L': {
                    'description': (
                        'Advanced First Two Layers - '
                        'Solve first two layers with advanced techniques.'
                    ),
                    'mode': 'af2l',
                },
            },
        },
        'Roux': {
            'cube_size': 3,
            'description': (
                'First Two Block, CMLL, LSE - '
                'The blockbuilding speedcubing method'
            ),
            'steps': {
                'CMLL': {
                    'description': (
                        'Corners of last layer - '
                        'Solve of corner orientations and permutations'
                    ),
                    'mode': 'cmll',
                },
                'LSE': {
                    'description': (
                        'Last Six Edges - '
                        'Solve M-slice centers and edges together'
                    ),
                    'mode': 'lse',
                },
            },
        },
        'Ortega': {
            'cube_size': 2,
            'description': (
                'Solve D, OLL, PBL - The most popular 2x2x2 method'
            ),
            'steps': {
                'OLL': {
                    'description': (
                        'Orientation of Last Layer - '
                        'Orient all pieces on the last layer'
                    ),
                    'mode': 'oll',
                },
                'PBL': {
                    'description': (
                        'Permutation of Both Layers - '
                        'Orient all pieces on all layers'
                    ),
                    'mode': '',
                },
            },
        },
    }

    def __init__(self, orientation: CubeOrientation = '', mode: str = '',
                 cube_size: str = '', palette: str = '') -> None:
        """
        Initialize academy overview view.

        Args:
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.orientation = orientation
        self.display_mode = mode
        self.cube_size = int(cube_size) if cube_size else 3
        self.palette = palette

    def get_display_context(self, default_mode: str = '') -> dict[
        str,
        str | Algorithm | dict[str, str] | int | list[str] | list[int]
        | list[tuple[str, list[str]]],
    ]:
        """
        Build shared display parameter context for academy views.

        Args:
            default_mode: Default mode when no GET override is provided.

        Returns:
            Dictionary with orientation, mode, cube size, and palette context.

        """
        orientation_faces = self.orientation or CUBE_ORIENTATION
        mode = self.display_mode or default_mode
        palette = self.palette or CUBE_PALETTE

        return {
            'orientation_faces': orientation_faces,
            'orientation_moves': get_orientation_moves(orientation_faces),
            'available_orientations': ORIENTATION_FACE_MOVES,
            'mode': mode,
            'available_modes': get_mode_groups(),
            'cube_size': self.cube_size,
            'available_cube_sizes': CUBE_SIZES,
            'palette': palette,
            'available_palettes': sorted(PALETTES.keys()),
        }

    def get_context(
            self,
    ) -> (
        AcademyOverviewContext
        | AcademyStepContext
        | AcademyCaseContext
        | TrainingReviewContext
    ):
        """
        Build context with available solving methods.

        Returns:
            Dictionary containing methods and their descriptions.

        """
        return cast(
            'AcademyOverviewContext',
            {
                'methods': self.methods,
                **self.get_display_context(),
            },
        )


class AcademyStepView(AcademyView):
    """View for displaying all cases for a specific method step."""

    template_name = 'academy/step.html'

    def __init__(  # noqa: PLR0913, PLR0917
            self, method: str, step: str, group: str, family: str,
            orientation: CubeOrientation, mode: str = '', cube_size: str = '',
            palette: str = '') -> None:
        """
        Initialize academy step view.

        Args:
            method: Method name (CFOP, Ortega).
            step: Method step name (F2L, OLL, or PLL).
            group: Step group filter.
            family: Step family filter.
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.method = method
        self.step = step
        self.group = group
        self.family = family
        self.orientation = orientation
        self.display_mode = mode
        self.palette = palette

        try:
            self.cases = get_collection(f'{ method }/{ step }').cases
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = (
                int(cube_size) if cube_size
                else self.methods[method]['cube_size']
            )
        except KeyError:
            abort(404, f'{ method }/{ step } does not exist')

        if group:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if group in case.groups
            }
        if family:
            self.cases = {
                c: case
                for c, case in self.cases.items()
                if family == case.family
            }

    @staticmethod
    def speed_band(ratio: float) -> str:
        """
        Classify the Ao5 of a case against the median of its step.

        Returns:
            Speed band, from ``fast-2`` to ``slow-2``.

        """
        for bound, band in SPEED_BANDS:
            if ratio <= bound:
                return band
        return SPEED_SLOWEST

    @staticmethod
    def memory_level(retention: float) -> str:
        """
        Classify the current recall probability of a case.

        Returns:
            Memory level, from ``0`` to ``4``.

        """
        for bound, level in MEMORY_LEVELS:
            if retention >= bound:
                return level
        return MEMORY_WEAKEST

    def build_training_tiles(
            self, trainings: Trainings, codes: list[str], now: datetime,
    ) -> dict[str, CaseTrainingTile]:
        """
        Build the training tint of every trained case of the step.

        Returns:
            Tile data keyed by case code, for trained cases only.

        """
        scheduler = FSRSScheduler()
        tiles: dict[str, CaseTrainingTile] = {}
        ao5s: dict[str, int] = {}

        for code in codes:
            case_training = trainings.cases.get(code)
            if case_training is None:
                continue

            stats = Statistics.from_milliseconds(case_training.timings)
            card = case_training.fsrs_card
            state_label, state_class = (
                fsrs_state_label(card) if card else ('New', 'new')
            )
            retention = (
                scheduler.retrievability(card, now) * 100
                if card and card.last_review else None
            )
            if stats.ao5 > 0:
                ao5s[code] = stats.ao5

            tiles[code] = {
                'state_label': state_label,
                'state_class': state_class,
                'overdue': card is not None and card.due <= now,
                'attempts': len(case_training.timings),
                'ao5': stats.ao5,
                'trend': stats.speed_trend,
                'speed': '',
                'memory': (
                    self.memory_level(retention)
                    if retention is not None else ''
                ),
                'retention': retention,
            }

        if len(ao5s) >= SPEED_MIN_CASES:
            median = Statistics(list(ao5s.values())).median
            for code, ao5 in ao5s.items():
                tiles[code]['speed'] = self.speed_band(ao5 / median)

        return tiles

    @staticmethod
    def build_state_row(
            label: str, count: int, overdue: int, bests: list[int],
            total: int,
    ) -> TrainingStateRow:
        """
        Build one row of the step training summary.

        Returns:
            Counts, share of the step and best timings of the row.

        """
        bests_ns = [best * MS_TO_NS_FACTOR for best in bests]
        return {
            'label': label,
            'klass': label.lower(),
            'count': count,
            'overdue': overdue,
            'share': count * 100 / total if total else 0.0,
            'offset': 0.0,
            'best': min(bests_ns, default=0),
            'average': round(sum(bests_ns) / len(bests_ns)) if bests_ns else 0,
            'worst': max(bests_ns, default=0),
        }

    def build_training_summary(
            self, trainings: Trainings, codes: list[str], now: datetime,
    ) -> StepTrainingSummary:
        """
        Recap the training of the step by card state.

        Same figures as the summary printed by the trainer: how many
        cases in each state, how many overdue, and the best, average and
        worst of their best timings.

        Returns:
            One row per populated state, laid end to end for a stacked
            bar, and a total row.

        """
        states = trainings.summarize_states(codes, now)
        total = len(codes)

        rows: list[TrainingStateRow] = []
        offset = 0.0
        for state in states.values():
            if not state.count:
                continue
            row = self.build_state_row(
                state.label, state.count, state.overdue, state.bests, total,
            )
            row['offset'] = offset
            offset += row['share']
            rows.append(row)

        everything = TrainingStateSummary(
            'Total',
            count=total,
            overdue=sum(state.overdue for state in states.values()),
            bests=[best for state in states.values() for best in state.bests],
        )

        return {
            'rows': rows,
            'total': self.build_state_row(
                everything.label, everything.count, everything.overdue,
                everything.bests, total,
            ),
        }

    def get_context(self) -> AcademyStepContext:
        """
        Build context with all cases for the step.

        Returns:
            Dictionary containing step information, case list, and the
            training of the cases when the step has a training file.

        """
        tree: dict[str, list[Case]] = {}
        cases = []
        for case in self.cases.values():
            if case.code != 'SKIP':
                tree.setdefault(case.family, []).append(case)
                cases.append(case)

        now = datetime.now(UTC)
        codes = [case.code for case in cases]
        trainings = read_trainings(self.method, self.step)

        return cast(
            'AcademyStepContext',
            {
                'method': self.method,
                'step': self.step,
                'step_info': self.step_info,
                'group': self.group,
                'family': self.family,
                'cases': cases,
                'tree': tree,
                'training': (
                    self.build_training_tiles(trainings, codes, now)
                    if trainings else {}
                ),
                'training_summary': (
                    self.build_training_summary(trainings, codes, now)
                    if trainings else None
                ),
                'training_unavailable': (
                    trainings is None
                    and trainings_path(self.method, self.step).exists()
                ),
                **self.get_display_context(
                    default_mode=self.step_info['mode'],
                ),
            },
        )


class AcademyCaseView(AcademyView):
    """View for displaying detailed information about a specific case."""

    template_name = 'academy/case.html'

    def __init__(  # noqa: PLR0913, PLR0917
            self, method: str, step: str, case_id: str,
            orientation: CubeOrientation, mode: str = '', cube_size: str = '',
            palette: str = '') -> None:
        """
        Initialize academy case view.

        Args:
            method: Method name (CFOP).
            step: CFOP step name (F2L, OLL, or PLL).
            case_id: Case identifier within the step.
            orientation: Cube orientation for display.
            mode: Display mode override.
            cube_size: Cube size override for display.
            palette: Color palette override.

        """
        self.method = method
        self.step = step
        self.case_id = case_id
        self.orientation = orientation
        self.display_mode = mode
        self.palette = palette

        try:
            self.case = get_case(f'{ method }/{ step }', case_id)
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = (
                int(cube_size) if cube_size
                else self.methods[method]['cube_size']
            )
        except KeyError:
            abort(404, f'{ method }/{ step } { case_id } does not exist')

    @staticmethod
    def build_attempts_curve(stats: Statistics) -> AttemptsCurve | None:
        """
        Build the timings of a case in attempt order.

        Timings are not dated, so the curve runs over attempts, with the
        rolling Ao5 and Ao12 of every attempt.

        Returns:
            Times and rolling averages in seconds, None without timing.

        """
        stack = stats.stack_time
        if not stack:
            return None

        ao5: list[float | None] = []
        ao12: list[float | None] = []
        for index in range(len(stack)):
            window = stack[:index + 1]
            for series, size in ((ao5, 5), (ao12, 12)):
                value = Statistics.ao(size, window)
                series.append(value / SECOND if value > 0 else None)

        peak = stats.best_ao12
        return {
            'labels': [str(index + 1) for index in range(len(stack))],
            'times': [time / SECOND for time in stack],
            'ao5': ao5,
            'ao12': ao12,
            'best': stats.best / SECOND,
            'peak': peak / SECOND if peak > 0 else None,
        }

    @staticmethod
    def build_forgetting_curve(
            case_training: CaseTraining, now: datetime,
    ) -> ForgettingCurve | None:
        """
        Sample the recall probability of a case since its last review.

        The curve runs from the last review past the later of today and
        the due date, horizontal axis in days since the last review.
        FSRS counts whole elapsed days, so the probability holds for a
        whole day: one sample per day, drawn as steps.

        Returns:
            Recall probability in percent over time, None when the case
            has never been reviewed.

        """
        card = case_training.fsrs_card
        if card is None or card.last_review is None:
            return None

        last_review = card.last_review
        today = (now - last_review).total_seconds() / DAY_SECONDS
        due = (card.due - last_review).total_seconds() / DAY_SECONDS
        span = ceil(max(today, due, 1.0) * (1 + FORGETTING_MARGIN))

        scheduler = FSRSScheduler()
        points: list[CurvePoint] = [
            {
                'x': days,
                'y': scheduler.retrievability(
                    card, last_review + timedelta(days=days),
                ) * 100,
            }
            for days in range(span + 1)
        ]

        return {
            'points': points,
            'today': today,
            'due': due,
            'retention': scheduler.retrievability(card, now) * 100,
        }

    def build_training_panel(
            self, case_training: CaseTraining,
    ) -> CaseTrainingPanel:
        """
        Build the personal training panel of the case.

        Returns:
            Statistics, FSRS card and curves of the case training.

        """
        now = datetime.now(UTC)
        stats = Statistics.from_milliseconds(case_training.timings)
        card = case_training.fsrs_card

        state_label, state_class = (
            fsrs_state_label(card) if card else ('New', 'new')
        )
        ratio = stats.peak_ratio

        return {
            'attempts': len(case_training.timings),
            'best': stats.best,
            'ao5': stats.ao5,
            'ao12': stats.ao12,
            'best_ao12': stats.best_ao12,
            'trend': stats.speed_trend,
            'trend_percent': round((ratio - 1) * 100) if ratio else 0,
            'last_date': datetime.fromtimestamp(
                case_training.last_date, tz=UTC,
            ).astimezone().strftime('%Y-%m-%d'),
            'state_label': state_label,
            'state_class': state_class,
            'stability': card.stability if card else None,
            'difficulty': card.difficulty if card else None,
            'last_review': (
                card.last_review.astimezone().strftime('%Y-%m-%d %H:%M')
                if card and card.last_review else ''
            ),
            'due': (
                card.due.astimezone().strftime('%Y-%m-%d %H:%M')
                if card else ''
            ),
            'due_relative': (
                format_relative_delay(card.due - now) if card else ''
            ),
            'overdue': card is not None and card.due <= now,
            'curve': self.build_attempts_curve(stats),
            'forgetting': self.build_forgetting_curve(case_training, now),
        }

    def get_context(self) -> AcademyCaseContext:
        """
        Build context with case details, algorithms, and orientations.

        Returns:
            Dictionary containing case information, and the personal
            training of the case when the step has a training file.

        """
        trainings = read_trainings(self.method, self.step)
        case_training = (
            trainings.cases.get(self.case.code) if trainings else None
        )

        return cast(
            'AcademyCaseContext',
            {
                'method': self.method,
                'step': self.step,
                'step_info': self.step_info,
                'case': self.case,
                'training': (
                    self.build_training_panel(case_training)
                    if case_training else None
                ),
                'training_unavailable': (
                    trainings is None
                    and trainings_path(self.method, self.step).exists()
                ),
                **self.get_display_context(
                    default_mode=self.step_info['mode'],
                ),
            },
        )


class AcademyCaseAlgorithmsDebugView(AcademyCaseView):
    """Debug view listing a case's algorithms with sortable scores."""

    template_name = 'academy/case_debug.html'

    def group_algorithms_by_impact(self) -> list[AlgorithmImpactGroup]:
        """
        Group the case algorithms by their real impact on the cube.

        Each algorithm is inverted and applied on a solved virtual cube;
        algorithms producing the same resulting state share the same impact
        and are grouped together, revealing real duplicates.

        Returns:
            Impact groups ordered by descending number of algorithms.

        """
        size = self.methods[self.method]['cube_size']

        grouped: dict[str, list[Algorithm]] = {}
        for algorithm in self.case.algorithms:
            cube = VCube(size=size)
            cube.rotate(algorithm.transform(invert_moves))
            grouped.setdefault(cube.state, []).append(algorithm)

        ordered_states = sorted(
            grouped.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )

        return [
            {
                'group_id': sha1(
                    state.encode(), usedforsecurity=False,
                ).hexdigest()[:8],
                'state': state,
                'algorithms': algorithms,
            }
            for state, algorithms in ordered_states
        ]

    def get_context(self) -> AcademyCaseAlgorithmsDebugContext:
        """
        Build context with case details and impact-grouped algorithms.

        Returns:
            Dictionary with case information and algorithm impact groups.

        """
        return cast(
            'AcademyCaseAlgorithmsDebugContext',
            {
                **super().get_context(),
                'impact_groups': self.group_algorithms_by_impact(),
            },
        )
