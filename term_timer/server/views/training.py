"""Training forecast view and dashboard banner."""
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from operator import itemgetter
from typing import TYPE_CHECKING
from typing import cast
from urllib.parse import urlencode

from bottle import abort
from cubing_algs.cases import get_collection
from cubing_algs.exceptions import InvalidCollectionNameError

from term_timer.formatter import format_relative_delay
from term_timer.fsrs.scheduler import FSRSScheduler
from term_timer.fsrs.storage import Trainings
from term_timer.in_out import list_training_steps
from term_timer.in_out import read_trainings
from term_timer.server.annotations import CaseFamily
from term_timer.server.annotations import CaseTile
from term_timer.server.annotations import ForecastSeries
from term_timer.server.annotations import ReviewPool
from term_timer.server.annotations import TrainingBannerInfo
from term_timer.server.annotations import TrainingForecast
from term_timer.server.annotations import TrainingForecastContext
from term_timer.server.annotations import TrainingReviewContext
from term_timer.server.annotations import TrainingStepRow
from term_timer.server.annotations import TrainingStepStatus
from term_timer.server.views.academy import AcademyView

if TYPE_CHECKING:
    from cubing_algs.annotations import CubeOrientation

# Steps in solving order; a step unknown here comes last, by name.
STEP_ORDER: tuple[str, ...] = (
    'CROSS', 'XCROSS', 'ECROSS', 'F2L', 'AF2L', 'OLL', 'PLL', 'LL',
)

# Color of each step in the forecast, fixed so that a step keeps its
# color whatever the others do. Any other step folds into OTHER_LABEL.
STEP_COLORS: dict[str, str] = {
    'F2L': '--chart-series-1',
    'OLL': '--chart-series-2',
    'PLL': '--chart-series-3',
}
OTHER_LABEL = 'Other'
OTHER_COLOR = '--chart-series-4'

# The same, as the chart series of each step.
STEP_SERIES: dict[str, int] = {'F2L': 1, 'OLL': 3, 'PLL': 4}
OTHER_SERIES = 5

# Days of the forecast after today, on top of the overdue column.
FORECAST_DAYS = 14

# Cases to rework shown on the training page, every step together.
WEAK_LIMIT = 12

# The choices of cases of the review sheet, the default first.
REVIEW_POOLS: tuple[tuple[str, str], ...] = (
    ('due', 'Due'),
    ('weak', 'To rework'),
    ('all', 'All'),
)


class TrainingForecastView(AcademyView):
    """View forecasting the reviews to come, step by step."""

    template_name = 'training.html'
    method = 'CFOP'

    @classmethod
    def read_steps(cls) -> dict[str, Trainings | None]:
        """
        Read the training file of every trained step.

        Returns:
            Trainings keyed by step in solving order, None for a file
            that cannot be read right now.

        """
        steps = sorted(
            list_training_steps(cls.method),
            key=lambda step: (
                STEP_ORDER.index(step) if step in STEP_ORDER
                else len(STEP_ORDER),
                step,
            ),
        )

        return {step: read_trainings(cls.method, step) for step in steps}

    @classmethod
    def collection_codes(cls, step: str) -> list[str] | None:
        """
        List the Academy cases of a step.

        Returns:
            Case codes of the step collection, None when the step has
            no Academy collection.

        """
        try:
            cases = get_collection(f'{ cls.method }/{ step }').cases
        except InvalidCollectionNameError:
            return None

        return [case.code for case in cases.values() if case.code != 'SKIP']

    @staticmethod
    def build_forecast(
            steps: dict[str, Trainings | None], now: datetime,
    ) -> TrainingForecast:
        """
        Count the reviews to come, day by day, for every carded step.

        Days are the calendar days of the timezone of ``now``: a review
        falls on the local day of its due date. Reviews already past
        their due date stack in a first overdue column.

        Returns:
            Day labels, one series of review counts per step, and the
            number of reviews beyond the forecast.

        """
        today = now.date()
        labels = ['Overdue', 'Today', 'Tomorrow']
        labels.extend(
            (today + timedelta(days=offset)).strftime('%a %d')
            for offset in range(2, FORECAST_DAYS)
        )

        series: dict[str, ForecastSeries] = {}
        later = 0

        for step, trainings in steps.items():
            if trainings is None:
                continue

            cards = [
                case.fsrs_card for case in trainings.cases.values()
                if case.fsrs_card is not None
            ]
            if not cards:
                continue

            label = step if step in STEP_COLORS else OTHER_LABEL
            entry = series.setdefault(label, {
                'label': label,
                'token': STEP_COLORS.get(step, OTHER_COLOR),
                'data': [0] * len(labels),
            })

            for card in cards:
                if card.due <= now:
                    entry['data'][0] += 1
                    continue

                offset = (card.due.astimezone(now.tzinfo).date() - today).days
                if offset < FORECAST_DAYS:
                    entry['data'][offset + 1] += 1
                else:
                    later += 1

        return {
            'labels': labels,
            'series': list(series.values()),
            'later': later,
        }

    @classmethod
    def build_status(
            cls, step: str, trainings: Trainings, now: datetime,
    ) -> TrainingStepStatus | None:
        """
        Sum up where the training of a step stands.

        The cases of a step are its Academy collection when it has one,
        the cases of its training file otherwise.

        Returns:
            Due, new and mastered counts of the step, None for a step
            without card nor Academy collection.

        """
        cards = {
            code: case.fsrs_card
            for code, case in trainings.cases.items()
            if case.fsrs_card is not None
        }
        codes = cls.collection_codes(step)
        if codes is None and not cards:
            return None

        academy = codes is not None
        if codes is None:
            codes = list(trainings.cases)

        mastered, total = FSRSScheduler.compute_mastery(
            cards, dict.fromkeys(codes, 0.0),
        )

        return {
            'step': step,
            'due': sum(1 for card in cards.values() if card.due <= now),
            'new': sum(1 for code in codes if code not in cards),
            'mastered': mastered,
            'total': total,
            'mastery': mastered * 100 / total if total else 0.0,
            'academy': academy,
        }

    @classmethod
    def build_banner(
            cls, steps: dict[str, Trainings | None], now: datetime,
    ) -> TrainingBannerInfo | None:
        """
        Build the training teaser from the trained steps.

        Returns:
            One status per trained step, None when nothing is trained.

        """
        statuses: list[TrainingStepStatus] = []
        unavailable: list[str] = []

        for step, trainings in steps.items():
            if trainings is None:
                unavailable.append(step)
                continue
            status = cls.build_status(step, trainings, now)
            if status is not None:
                statuses.append(status)

        if not statuses and not unavailable:
            return None

        return {
            'steps': statuses,
            'due': sum(status['due'] for status in statuses),
            'unavailable': unavailable,
        }

    @classmethod
    def banner(cls) -> TrainingBannerInfo | None:
        """
        Build the training teaser shown on the dashboard.

        Returns:
            One status per trained step, None when nothing is trained.

        """
        return cls.build_banner(cls.read_steps(), datetime.now().astimezone())

    def build_step_rows(
            self, steps: dict[str, Trainings | None],
            banner: TrainingBannerInfo | None, now: datetime,
    ) -> list[TrainingStepRow]:
        """
        Build the trained steps with their cases by card state.

        Returns:
            One row per step of the banner, in solving order.

        """
        rows: list[TrainingStepRow] = []
        for status in banner['steps'] if banner else []:
            step = status['step']
            trainings = steps[step]
            if trainings is None:
                continue
            codes = self.collection_codes(step) or list(trainings.cases)
            academy = status['academy']
            rows.append({
                'status': status,
                'states': self.build_training_summary(
                    trainings, codes, now,
                )['rows'],
                'command': self.train_command(self.method, step),
                'academy_url': (
                    self.step_url(self.method, step) if academy else ''
                ),
                'review_url': (
                    self.review_url(self.method, step) if academy else ''
                ),
            })
        return rows

    def build_weak(
            self, steps: dict[str, Trainings | None], now: datetime,
    ) -> list[CaseTile]:
        """
        Pick the cases to rework across the steps of the Academy.

        Returns:
            At most WEAK_LIMIT tiles, the lowest recall first.

        """
        weak: list[tuple[float, CaseTile]] = []
        for step, trainings in steps.items():
            if trainings is None or step not in self.methods[
                    self.method]['steps']:
                continue
            cases = {
                case.code: case
                for case in self.collection_cases(self.method, step)
            }
            tiles = self.build_training_tiles(trainings, list(cases), now)
            for code in self.weak_codes(tiles):
                training = tiles[code]
                retention = training['retention']
                tile = self.build_tile(
                    cases[code], training, trainings.cases[code].solution,
                )
                # Codes repeat from a step to another: 01 is an F2L and
                # an OLL case.
                tile['label'] = ' · '.join(
                    part for part in (step, tile['label']) if part
                )
                weak.append((
                    retention if retention is not None else 100.0, tile,
                ))

        weak.sort(key=itemgetter(0))
        return [tile for _retention, tile in weak[:WEAK_LIMIT]]

    def get_context(self) -> TrainingForecastContext:
        """
        Build context with the step statuses and the review forecast.

        Returns:
            Dictionary with the banner statuses, the forecast, the steps
            by card state and the cases to rework.

        """
        now = datetime.now().astimezone()
        steps = self.read_steps()
        banner = self.build_banner(steps, now)
        display = self.get_display_context()
        forecast = self.build_forecast(steps, now)
        legend = [
            (STEP_SERIES.get(series['label'], OTHER_SERIES), series['label'])
            for series in forecast['series']
        ]

        return {
            'banner': banner,
            'forecast': forecast,
            'forecast_chart': {
                'labels': forecast['labels'],
                'series': [
                    {
                        'label': series['label'],
                        'role': f'chart-{ key }',
                        'data': series['data'],
                    }
                    for (key, _label), series in zip(
                        legend, forecast['series'], strict=True,
                    )
                ],
            },
            'forecast_legend': legend,
            'steps': self.build_step_rows(steps, banner, now),
            'weak': self.build_weak(steps, now),
            'orientation_faces': cast(
                'CubeOrientation', display['orientation_faces'],
            ),
            'palette': cast('str', display['palette']),
        }


class TrainingReviewView(AcademyView):
    """
    View of the review sheet of a step.

    The cases to train next, each with the algorithm to execute, to
    refresh them before a session on the cube. Read only, nothing is
    rated: a review without the cube would bias the FSRS calibration.
    """

    template_name = 'training_review.html'

    def __init__(self, method: str, step: str, pool: str = '',
                 family: str = '') -> None:
        """
        Initialize the review view of a step.

        Args:
            method: Method name (CFOP).
            step: Step name of the Academy (F2L, OLL, PLL...).
            pool: Cases to review: due (default), weak or all.
            family: Family the cases are restricted to, if any.

        """
        super().__init__()
        self.method = method
        self.step = step
        self.pool = pool if pool in dict(REVIEW_POOLS) else 'due'
        self.family = family

        try:
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = self.methods[method]['cube_size']
            get_collection(f'{ method }/{ step }')
        except (KeyError, InvalidCollectionNameError):
            abort(404, f'{ method }/{ step } does not exist')

    def pool_codes(
            self, trainings: Trainings | None, codes: list[str],
            now: datetime,
    ) -> dict[str, list[str]]:
        """
        Order the cases of every pool of the review sheet.

        Returns:
            The codes of each pool: due, the most overdue first; weak,
            the lowest recall first; all, in collection order.

        """
        if trainings is None:
            return {'due': [], 'weak': [], 'all': codes}

        due: list[tuple[datetime, str]] = []
        for code in codes:
            case_training = trainings.cases.get(code)
            card = case_training.fsrs_card if case_training else None
            if card is not None and card.due <= now:
                due.append((card.due, code))
        due.sort()
        tiles = self.build_training_tiles(trainings, codes, now)

        return {
            'due': [code for _due, code in due],
            'weak': self.weak_codes(tiles),
            'all': codes,
        }

    def sheet_url(self, pool: str, family: str) -> str:
        """
        Locate the review sheet of the step for a pool and a family.

        Returns:
            The URL, without query for the due cases of every family.

        """
        base = self.review_url(self.method, self.step)
        parameters = {
            key: value
            for key, value in (('pool', pool), ('family', family))
            if value and value != 'due'
        }
        return f'{ base }?{ urlencode(parameters) }' if parameters else base

    def build_sheet(
            self, now: datetime,
    ) -> tuple[list[ReviewPool], list[CaseFamily], list[CaseTile]]:
        """
        Build the review sheet: its pools, its families and its cases.

        Returns:
            The pools with their counts, the families to restrict them
            to, and the tiles of the chosen pool and family.

        """
        trainings = read_trainings(self.method, self.step)
        cases = {
            case.code: case
            for case in self.collection_cases(self.method, self.step)
        }
        shown = [
            code for code, case in cases.items()
            if not self.family or case.family == self.family
        ]
        pools = self.pool_codes(trainings, shown, now)
        training = (
            self.build_training_tiles(trainings, list(cases), now)
            if trainings else {}
        )
        tiles: list[CaseTile] = []
        for code in pools[self.pool]:
            case_training = trainings.cases.get(code) if trainings else None
            card = case_training.fsrs_card if case_training else None
            tiles.append(self.build_tile(
                cases[code], training.get(code),
                case_training.solution if case_training else '',
                note=(
                    format_relative_delay(card.due - now)
                    if self.pool == 'due' and card else ''
                ),
            ))

        return (
            [
                {
                    'slug': slug,
                    'label': label,
                    'href': self.sheet_url(slug, self.family),
                    'count': len(pools[slug]),
                    'active': slug == self.pool,
                }
                for slug, label in REVIEW_POOLS
            ],
            [
                {
                    'name': name,
                    'slug': name.lower().replace(' ', '-'),
                    'href': self.sheet_url(self.pool, name),
                    'active': name == self.family,
                    'tiles': [],
                }
                for name in dict.fromkeys(
                    case.family for case in cases.values()
                )
            ],
            tiles,
        )

    def get_context(self) -> TrainingReviewContext:
        """
        Build context with the review sheet.

        Returns:
            Dictionary with the step, its sheet and the display
            parameters of the case images.

        """
        display = self.get_display_context(
            default_mode=self.step_info['mode'],
        )
        now = datetime.now(UTC)
        pools, families, tiles = self.build_sheet(now)

        return {
            'method': self.method,
            'step': self.step,
            'breadcrumb': [
                {'label': 'Training', 'href': '/training/'},
                {
                    'label': f'{ self.method } { self.step }',
                    'href': self.step_url(self.method, self.step),
                },
                {'label': 'Review', 'href': ''},
            ],
            'pool': self.pool,
            'pools': pools,
            'family': self.family,
            'families': families,
            'families_url': self.sheet_url(self.pool, ''),
            'tiles': tiles,
            'command': self.train_command(
                self.method, self.step,
                tuple(tile['code'] for tile in tiles)
                if self.pool != 'due' and tiles else (),
            ),
            'orientation_faces': cast(
                'CubeOrientation', display['orientation_faces'],
            ),
            'palette': cast('str', display['palette']),
        }
