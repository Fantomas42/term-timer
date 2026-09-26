"""Training forecast view and dashboard banner."""
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from operator import itemgetter
from typing import TYPE_CHECKING
from typing import cast

from bottle import abort
from cubing_algs.cases import get_collection
from cubing_algs.exceptions import InvalidCollectionNameError

from term_timer.formatter import format_relative_delay
from term_timer.formatter import fsrs_state_label
from term_timer.fsrs.scheduler import FSRSScheduler
from term_timer.fsrs.storage import Trainings
from term_timer.in_out import list_training_steps
from term_timer.in_out import read_trainings
from term_timer.server.annotations import ForecastSeries
from term_timer.server.annotations import ReviewCard
from term_timer.server.annotations import TrainingBannerInfo
from term_timer.server.annotations import TrainingForecast
from term_timer.server.annotations import TrainingForecastContext
from term_timer.server.annotations import TrainingReviewContext
from term_timer.server.annotations import TrainingStepStatus
from term_timer.server.views.academy import AcademyView
from term_timer.server.views.base import View

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

# Days of the forecast after today, on top of the overdue column.
FORECAST_DAYS = 14


class TrainingForecastView(View):
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

    def get_context(self) -> TrainingForecastContext:
        """
        Build context with the step statuses and the review forecast.

        Returns:
            Dictionary with the banner statuses and the forecast.

        """
        now = datetime.now().astimezone()
        steps = self.read_steps()

        return {
            'banner': self.build_banner(steps, now),
            'forecast': self.build_forecast(steps, now),
        }


class TrainingReviewView(AcademyView):
    """
    View serving the due cases of a step as flashcards.

    Recognition practice away from the cube: the case is shown, its
    algorithm hidden until asked for. Read only, nothing is rated: a
    review without the cube would bias the FSRS calibration.
    """

    template_name = 'training_review.html'

    def __init__(self, method: str, step: str) -> None:
        """
        Initialize the review view of a step.

        Args:
            method: Method name (CFOP).
            step: Step name of the Academy (F2L, OLL, PLL...).

        """
        super().__init__()
        self.method = method
        self.step = step

        try:
            self.step_info = self.methods[method]['steps'][step]
            self.cube_size = self.methods[method]['cube_size']
            self.cases = get_collection(f'{ method }/{ step }').cases
        except (KeyError, InvalidCollectionNameError):
            abort(404, f'{ method }/{ step } does not exist')

    def build_cards(self, now: datetime) -> list[ReviewCard]:
        """
        Build a flashcard for every due case of the step.

        Returns:
            Due cases, the most overdue first, with the algorithm to
            reveal: the solution saved while training, or the main one.

        """
        trainings = read_trainings(self.method, self.step)
        if trainings is None:
            return []

        by_code = {case.code: case for case in self.cases.values()}
        due = sorted(
            (
                (case_training.fsrs_card.due, code, case_training)
                for code, case_training in trainings.cases.items()
                if case_training.fsrs_card is not None
                and case_training.fsrs_card.due <= now
                and code in by_code
            ),
            key=itemgetter(0),
        )

        cards: list[ReviewCard] = []
        for due_date, code, case_training in due:
            case = by_code[code]
            card = case_training.fsrs_card
            state_label, state_class = (
                fsrs_state_label(card) if card else ('New', 'new')
            )
            cards.append({
                'code': code,
                'name': case.pretty_name,
                'main_algorithm': str(case.main_algorithm),
                'arrows': case.arrows,
                'algorithm': (
                    case_training.solution or str(case.main_algorithm)
                ),
                'overdue': format_relative_delay(due_date - now),
                'state_label': state_label,
                'state_class': state_class,
            })

        return cards

    def get_context(self) -> TrainingReviewContext:
        """
        Build context with the flashcards of the due cases.

        Returns:
            Dictionary with the step, its flashcards and the display
            parameters of the case images.

        """
        display = self.get_display_context(
            default_mode=self.step_info['mode'],
        )

        return {
            'method': self.method,
            'step': self.step,
            'cards': self.build_cards(datetime.now(UTC)),
            'orientation_faces': cast(
                'CubeOrientation', display['orientation_faces'],
            ),
            'mode': cast('str', display['mode']),
            'cube_size': self.cube_size,
            'palette': cast('str', display['palette']),
        }
