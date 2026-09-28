"""Academy overview, step, and case views."""
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from hashlib import sha1
from math import ceil
from typing import TYPE_CHECKING
from typing import ClassVar
from typing import Self
from typing import cast
from urllib.parse import quote
from urllib.parse import urlencode

from bottle import abort
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.exceptions import InvalidCaseNameError
from cubing_algs.exceptions import InvalidCollectionNameError
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

if TYPE_CHECKING:
    from cubing_algs.cases.case import Case
    from fsrs import Card
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
from term_timer.server.annotations import AcademyMethodCard
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepCard
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AlgorithmImpactGroup
from term_timer.server.annotations import AlgorithmRow
from term_timer.server.annotations import AlgorithmSource
from term_timer.server.annotations import AttemptsCurve
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import CaseAlgorithmFocus
from term_timer.server.annotations import CaseFamily
from term_timer.server.annotations import CaseTile
from term_timer.server.annotations import CaseTrainingPanel
from term_timer.server.annotations import CaseTrainingTile
from term_timer.server.annotations import CurvePoint
from term_timer.server.annotations import ForgettingCurve
from term_timer.server.annotations import MethodInfo
from term_timer.server.annotations import PlayerData
from term_timer.server.annotations import RecognitionAngle
from term_timer.server.annotations import StepCounts
from term_timer.server.annotations import StepTrainingSummary
from term_timer.server.annotations import TrainingForecastContext
from term_timer.server.annotations import TrainingReviewContext
from term_timer.server.annotations import TrainingStateRow
from term_timer.server.filters import algorithm_tokens
from term_timer.server.filters import paragraphs
from term_timer.server.filters import sort_algorithms
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

# A case to rework: its recall probability fell under this percentage,
# or its Ao5 drifted well above its best Ao12.
WEAK_RECALL = 90.0

# The steps the trainer knows, by method: only those get a command.
TRAINABLE_STEPS: dict[str, frozenset[str]] = {
    'CFOP': frozenset({'F2L', 'AF2L', 'OLL', 'PLL'}),
}

# The four 3D views of the recognition angles, around the top face.
RECOGNITION_ROTATIONS = ('y45x-34', 'y135x-34', 'y225x-34', 'y315x-34')


class AcademyView(View):
    """View for displaying academy overview with solving methods."""

    template_name = 'v2/academy.html'
    legacy_template = 'academy/overview.html'
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

    def legacy(self, *, v1: bool) -> Self:
        """
        Render the V1 page instead, kept to compare with the V2 one until
        the V1 is removed.

        Args:
            v1: Whether the V1 page is asked for, by ?v1 in the URL.

        Returns:
            The view itself.

        """
        if v1:
            self.template_name = self.legacy_template
        return self

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

    def display_query(self) -> str:
        """
        Carry the display overrides of the page to the pages it links.

        Returns:
            The query string of the overrides given, empty without any.

        """
        overrides = {
            'o': self.orientation,
            'm': self.display_mode,
            'p': self.palette,
        }
        query = urlencode({key: value for key, value in overrides.items()
                           if value})
        return f'?{ query }' if query else ''

    @staticmethod
    def step_url(method: str, step: str) -> str:
        """
        Locate the academy page of a step.

        Returns:
            The URL of the step page.

        """
        return f'/academy/{ method }/{ step }/'

    @classmethod
    def case_url(cls, method: str, step: str, code: str) -> str:
        """
        Locate the academy page of a case.

        Returns:
            The URL of the case page.

        """
        return f'{ cls.step_url(method, step) }{ quote(code) }/'

    @staticmethod
    def review_url(method: str, step: str) -> str:
        """
        Locate the review sheet of a step.

        Returns:
            The URL of the review sheet.

        """
        return f'/training/{ method }/{ step }/review/'

    @staticmethod
    def train_command(
            method: str, step: str, codes: tuple[str, ...] = (),
    ) -> str:
        """
        Word the command training a step, restricted to some cases.

        Returns:
            The command, empty for a step the trainer does not know.

        """
        if step not in TRAINABLE_STEPS.get(method, frozenset()):
            return ''
        command = f'term-timer train -s { step.lower() }'
        if codes:
            command += ' -c ' + ' '.join(codes)
        return command

    @staticmethod
    def split_description(description: str) -> tuple[str, str]:
        """
        Split a description into its title and its explanation.

        Returns:
            The part before the dash, the part after, or the whole as a
            title when there is no dash.

        """
        title, _dash, explanation = description.partition(' - ')
        return title, explanation

    @staticmethod
    def collection_cases(method: str, step: str) -> list['Case']:
        """
        List the cases of a step, the skip aside.

        Returns:
            The cases in collection order, empty without collection.

        """
        try:
            cases = get_collection(f'{ method }/{ step }').cases
        except InvalidCollectionNameError:
            return []
        return [case for case in cases.values() if case.code != 'SKIP']

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
    def weak_codes(tiles: dict[str, CaseTrainingTile]) -> list[str]:
        """
        Pick the cases to rework among trained ones.

        A case is weak when its recall probability fell under
        WEAK_RECALL, or when its Ao5 drifted well above its best Ao12.

        Returns:
            The weak case codes, the lowest recall first.

        """
        weak = [
            code for code, tile in tiles.items()
            if (tile['retention'] is not None
                and tile['retention'] < WEAK_RECALL)
            or tile['trend'] == 'down'
        ]

        def recall(code: str) -> float:
            retention = tiles[code]['retention']
            return retention if retention is not None else 100.0

        return sorted(weak, key=recall)

    @staticmethod
    def build_counts(
            trainings: Trainings, codes: list[str], now: datetime,
    ) -> StepCounts:
        """
        Count how far the training of the given cases went.

        Returns:
            The cases, the trained, mastered and due ones among them.

        """
        cards: dict[str, Card] = {}
        for code in codes:
            case_training = trainings.cases.get(code)
            if case_training is not None and case_training.fsrs_card:
                cards[code] = case_training.fsrs_card
        mastered, total = FSRSScheduler.compute_mastery(
            cards, dict.fromkeys(codes, 0.0),
        )

        return {
            'cases': total,
            'trained': sum(1 for code in codes if code in trainings.cases),
            'mastered': mastered,
            'due': sum(1 for card in cards.values() if card.due <= now),
        }

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

    def build_tile(
            self, case: 'Case', training: CaseTrainingTile | None,
            solution: str = '', note: str = '',
    ) -> CaseTile:
        """
        Build the tile of a case in a grid.

        Args:
            case: The case, knowing its method and step.
            training: Training of the case, None when never trained.
            solution: Solution saved in the training file, if any.
            note: A short remark shown on the tile.

        Returns:
            What the tile shows, with the algorithm to execute: the
            solution when there is one, the main algorithm otherwise.

        """
        method, step = case.method, case.step
        method_info = self.methods[method]
        _code, _space, label = case.pretty_name.partition(' (')

        return {
            'code': case.code,
            'label': label.removesuffix(')'),
            'href': (
                self.case_url(method, step, case.code) + self.display_query()
            ),
            'family': case.family,
            'image': str(case.main_algorithm),
            'arrows': case.arrows,
            'mode': (
                self.display_mode or method_info['steps'][step]['mode']
            ),
            'cube_size': method_info['cube_size'],
            'tokens': algorithm_tokens(solution or case.main_algorithm),
            'custom': bool(solution),
            'probability': case.probability_label,
            'algorithms': len(case.algorithms),
            'note': note,
            'training': training,
        }

    def build_method_cards(self, now: datetime) -> list[AcademyMethodCard]:
        """
        Build the methods of the overview, each step with its training.

        Returns:
            One card per method, its steps in teaching order.

        """
        cards: list[AcademyMethodCard] = []
        for name, info in self.methods.items():
            steps: list[AcademyStepCard] = []
            for step, step_info in info['steps'].items():
                cases = self.collection_cases(name, step)
                codes = [case.code for case in cases]
                trainings = read_trainings(name, step)
                title, explanation = self.split_description(
                    step_info['description'],
                )
                steps.append({
                    'step': step,
                    'title': title,
                    'description': explanation,
                    'href': self.step_url(name, step) + self.display_query(),
                    'mode': self.display_mode or step_info['mode'],
                    'cases': len(cases),
                    'image': str(cases[0].main_algorithm) if cases else '',
                    'arrows': cases[0].arrows if cases else '',
                    'counts': (
                        self.build_counts(trainings, codes, now)
                        if trainings else None
                    ),
                    'states': (
                        self.build_training_summary(
                            trainings, codes, now,
                        )['rows']
                        if trainings else []
                    ),
                    'review_url': (
                        self.review_url(name, step) if trainings else ''
                    ),
                })

            title, explanation = self.split_description(info['description'])
            cards.append({
                'name': name,
                'slug': name.lower(),
                'cube_size': info['cube_size'],
                'title': title,
                'description': explanation,
                'steps': steps,
            })

        return cards

    def get_context(
            self,
    ) -> (
        AcademyOverviewContext
        | AcademyStepContext
        | AcademyCaseContext
        | TrainingForecastContext
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
                'method_cards': self.build_method_cards(datetime.now(UTC)),
                **self.get_display_context(),
            },
        )


class AcademyStepView(AcademyView):
    """View for displaying all cases for a specific method step."""

    template_name = 'v2/academy_step.html'
    legacy_template = 'academy/step.html'

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
            self.all_cases = get_collection(f'{ method }/{ step }').cases
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = (
                int(cube_size) if cube_size
                else self.methods[method]['cube_size']
            )
        except (KeyError, InvalidCollectionNameError):
            abort(404, f'{ method }/{ step } does not exist')

        self.cases = self.all_cases
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

    def build_families(
            self, tree: dict[str, list['Case']],
            training: dict[str, CaseTrainingTile],
            solutions: dict[str, str],
    ) -> list[CaseFamily]:
        """
        Build every family of the step, the cases of the shown ones.

        Every family of the collection is listed, to filter on; only
        the families left by the filters carry their tiles.

        Returns:
            The families in collection order.

        """
        base = self.step_url(self.method, self.step)
        names = list(dict.fromkeys(
            case.family for case in self.all_cases.values()
            if case.code != 'SKIP'
        ))

        return [
            {
                'name': name,
                'slug': name.lower().replace(' ', '-') or 'other',
                'href': f'{ base }?{ urlencode({"family": name}) }',
                'active': name == self.family,
                'tiles': [
                    self.build_tile(
                        case, training.get(case.code),
                        solutions.get(case.code, ''),
                    )
                    for case in tree.get(name, [])
                ],
            }
            for name in names
        ]

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
        training = (
            self.build_training_tiles(trainings, codes, now)
            if trainings else {}
        )
        solutions = {
            code: case_training.solution
            for code, case_training in (
                trainings.cases.items() if trainings else ()
            )
            if case_training.solution
        }
        step_url = self.step_url(self.method, self.step)

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
                'training': training,
                'training_summary': (
                    self.build_training_summary(trainings, codes, now)
                    if trainings else None
                ),
                'training_unavailable': (
                    trainings is None
                    and trainings_path(self.method, self.step).exists()
                ),
                'breadcrumb': [
                    {'label': 'Academy', 'href': '/academy/'},
                    {'label': f'{ self.method } { self.step }', 'href': ''},
                ],
                'families': self.build_families(tree, training, solutions),
                'counts': (
                    self.build_counts(trainings, codes, now)
                    if trainings else None
                ),
                'all_url': step_url,
                'review_url': (
                    self.review_url(self.method, self.step)
                    if trainings else ''
                ),
                'command': self.train_command(self.method, self.step),
                **self.get_display_context(
                    default_mode=self.step_info['mode'],
                ),
            },
        )


class AcademyCaseView(AcademyView):
    """View for displaying detailed information about a specific case."""

    template_name = 'v2/academy_case.html'
    legacy_template = 'academy/case.html'

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
        except (KeyError, InvalidCollectionNameError, InvalidCaseNameError):
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

    def neighbour_urls(self) -> tuple[str, str]:
        """
        Locate the cases before and after this one in its step.

        Returns:
            The URLs of the previous and next cases, empty at the ends.

        """
        codes = [
            case.code
            for case in self.collection_cases(self.method, self.step)
        ]
        if self.case.code not in codes:
            return '', ''

        index = codes.index(self.case.code)
        query = self.display_query()

        def url(position: int) -> str:
            if 0 <= position < len(codes):
                return (
                    self.case_url(self.method, self.step, codes[position])
                    + query
                )
            return ''

        return url(index - 1), url(index + 1)

    @staticmethod
    def algorithm_rows(algorithms: list[Algorithm]) -> list[AlgorithmRow]:
        """
        Rank algorithms, the most comfortable first, with their scores.

        Returns:
            One row per algorithm, ranked by ergonomics then memory.

        """
        rows: list[AlgorithmRow] = []
        for rank, algorithm in enumerate(sort_algorithms(algorithms), 1):
            tokens = algorithm_tokens(algorithm)
            rows.append({
                'rank': rank,
                'text': str(algorithm),
                'tokens': tokens,
                'htm': algorithm.metrics.htm,
                'ergonomics': algorithm.ergonomics.ergonomic_score * 100,
                'memory': algorithm.memory.memory_score * 100,
                'href': f'/algorithm/{ algorithm }/',
            })
        return rows

    def build_sources(self) -> list[AlgorithmSource]:
        """
        Gather the algorithms of the case, one table per source.

        Returns:
            The sources holding at least one algorithm.

        """
        badmephisto = self.case.badmephisto
        comment = (
            ' '.join(badmephisto['comment'].split()) if badmephisto else ''
        )
        difficulty = badmephisto['difficulty'] if badmephisto else 0
        note = comment
        if difficulty:
            note = f'Difficulty { difficulty } / 5. { comment }'.strip()

        sources: list[AlgorithmSource] = [
            {
                'slug': 'database',
                'label': 'Database',
                'note': (
                    'Every algorithm known for the case, the most'
                    ' comfortable first.'
                ),
                'image': 'case',
                'rows': self.algorithm_rows(self.case.algorithms),
            },
            {
                'slug': 'badmephisto',
                'label': 'BadMephisto',
                'note': note,
                'image': 'case',
                'rows': self.algorithm_rows(
                    badmephisto['algos'] if badmephisto else [],
                ),
            },
            {
                'slug': 'two-phase',
                'label': 'Two-phase',
                'note': 'Computed by the two-phase solver.',
                'image': 'case',
                'rows': self.algorithm_rows(
                    self.case.two_phase_algorithms,
                ),
            },
            {
                'slug': 'setups',
                'label': 'Setups',
                'note': 'Sequences setting the case up on a solved cube.',
                'image': 'algo',
                'rows': self.algorithm_rows(self.case.setup_algorithms),
            },
        ]

        return [source for source in sources if source['rows']]

    def build_recognition(self) -> list[RecognitionAngle]:
        """
        List the angles the case is recognised from.

        Returns:
            One angle per recognition case, with its 3D rotation.

        """
        recognition = self.case.recognition
        if recognition is None:
            return []

        return [
            {
                'feature': angle['feature']['name'],
                'feature_notes': paragraphs(angle['feature']['description']),
                'description': paragraphs(angle['description']),
                'observation': angle['observation'],
                'notes': angle['notes'],
                'rotation': RECOGNITION_ROTATIONS[
                    index % len(RECOGNITION_ROTATIONS)
                ],
            }
            for index, angle in enumerate(recognition['cases'])
        ]

    def build_focus(self, solution: str) -> CaseAlgorithmFocus:
        """
        Describe the algorithm to learn for the case.

        Returns:
            The solution saved while training when there is one, taken
            as it is like the trainer does, the main algorithm otherwise.

        """
        algorithm = (
            parse_moves(solution, trust_input=True)
            if solution else self.case.main_algorithm
        )
        tokens = algorithm_tokens(algorithm)

        return {
            'text': str(algorithm),
            'tokens': tokens,
            'custom': bool(solution),
            'htm': algorithm.metrics.htm,
            'stm': algorithm.metrics.stm,
            'ergonomics': algorithm.ergonomics.ergonomic_score * 100,
            'memory': algorithm.memory.memory_score * 100,
            'href': f'/algorithm/{ algorithm }/',
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
        display = self.get_display_context(
            default_mode=self.step_info['mode'],
        )
        focus = self.build_focus(
            case_training.solution if case_training else '',
        )
        previous_url, next_url = self.neighbour_urls()
        player: PlayerData = {
            'alg': focus['text'],
            'setup': str(display['orientation_moves']),
            'anchor': 'end',
            'puzzle': f'{ self.cube_size }x{ self.cube_size }x'
                      f'{ self.cube_size }',
            'timing': [],
            'index': {},
        }
        crumbs: list[BreadcrumbItem] = [
            {'label': 'Academy', 'href': '/academy/'},
            {
                'label': f'{ self.method } { self.step }',
                'href': (
                    self.step_url(self.method, self.step)
                    + self.display_query()
                ),
            },
            {'label': self.case.code, 'href': ''},
        ]
        recognition = self.case.recognition
        sources = self.build_sources()

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
                'breadcrumb': crumbs,
                'previous_url': previous_url,
                'next_url': next_url,
                'focus': focus,
                'sources': sources,
                'source_tabs': [
                    (source['slug'], source['label']) for source in sources
                ],
                'step_url': self.step_url(self.method, self.step),
                'recognition': self.build_recognition(),
                'recognition_setup': (
                    ' '.join(recognition['moves']) if recognition else ''
                ),
                'description': paragraphs(self.case.description),
                'player': player,
                'command': self.train_command(
                    self.method, self.step, (self.case.code,),
                ),
                **display,
            },
        )


class AcademyCaseAlgorithmsDebugView(AcademyCaseView):
    """Debug view listing a case's algorithms with sortable scores."""

    template_name = 'v2/academy_case_debug.html'
    legacy_template = 'academy/case_debug.html'

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
        context = super().get_context()
        crumbs = [
            *context['breadcrumb'][:-1],
            {
                'label': self.case.code,
                'href': (
                    self.case_url(self.method, self.step, self.case.code)
                    + self.display_query()
                ),
            },
            {'label': 'Algorithms', 'href': ''},
        ]

        return cast(
            'AcademyCaseAlgorithmsDebugContext',
            {
                **context,
                'breadcrumb': crumbs,
                'impact_groups': self.group_algorithms_by_impact(),
            },
        )
