"""Training interface for practicing specific CFOP cases."""
import asyncio
import math
from datetime import UTC
from datetime import datetime
from operator import itemgetter
from random import Random
from typing import TYPE_CHECKING
from typing import Final
from typing import NamedTuple

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.cases import get_collection
from cubing_algs.cases.case import Case
from cubing_algs.constants import DEFAULT_CUBE_SIZE
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.vcube import VCube
from fsrs import Rating
from fsrs import State
from rich import box
from rich.table import Table

from term_timer.annotations import TrainingCase
from term_timer.config import DEBUG
from term_timer.config import STATS_LIVE_SERIES
from term_timer.config import STATS_SESSION_SERIES
from term_timer.config import TRAINER_FSRS
from term_timer.config import TRAINER_FSRS_RATING
from term_timer.constants import CROSS_CASE
from term_timer.constants import DNF
from term_timer.constants import EASY_CROSS_CASE
from term_timer.constants import ESCAPE_CHAR
from term_timer.constants import LL_CASE
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import X_CROSS_CASE
from term_timer.constants import SolveFlag
from term_timer.exceptions import InvalidCaseError
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_fluency
from term_timer.formatter import format_fsrs_due
from term_timer.formatter import format_fsrs_state
from term_timer.formatter import format_term_timer_case_url
from term_timer.formatter import format_time
from term_timer.formatter import fsrs_state_label
from term_timer.fsrs.rating import BAND_AGAIN
from term_timer.fsrs.rating import BAND_EASY
from term_timer.fsrs.rating import BAND_GOOD
from term_timer.fsrs.rating import HIGH_STABILITY_FLOOR_DAYS
from term_timer.fsrs.rating import MISSED_WEIGHT
from term_timer.fsrs.rating import PAUSE_TOLERANCE
from term_timer.fsrs.rating import PAUSE_WEIGHT
from term_timer.fsrs.rating import TIME_SCALE
from term_timer.fsrs.rating import TPS_SCALE
from term_timer.fsrs.rating import PerformanceRater
from term_timer.fsrs.rating import RatingBreakdown
from term_timer.fsrs.scheduler import FSRSScheduler
from term_timer.fsrs.storage import CaseTraining
from term_timer.in_out import load_trainings
from term_timer.in_out import save_trainings
from term_timer.interface import SolveInterface
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import FaceletAnalyser
from term_timer.printer import print_cube_trainer
from term_timer.scrambler import trainer
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.triggers import DEFAULT_TRIGGERS

if TYPE_CHECKING:
    from fsrs import Card


class StepDef(NamedTuple):
    """Definition of a training step."""

    step_code: str
    printer_mode: str
    display_name: str
    training_case: TrainingCase | None = None


STEP_CONFIGS: Final[dict[str, StepDef]] = {
    'cross': StepDef(
        'Cross', 'cross', 'Cross',
        TrainingCase(CROSS_CASE, []),
    ),
    'xcross': StepDef(
        'Cross', 'cross', 'X-Cross',
        TrainingCase(X_CROSS_CASE, []),
    ),
    'ecross': StepDef(
        'Cross', 'cross', 'Easy Cross',
        TrainingCase(EASY_CROSS_CASE, []),
    ),
    'll': StepDef(
        'PLL', 'll', 'LL',
        TrainingCase(LL_CASE, []),
    ),
    'oll': StepDef('OLL', 'oll', 'OLL'),
    'pll': StepDef('PLL', 'pll', 'PLL'),
    'f2l': StepDef('F2L', 'f2l', 'F2L'),
    'af2l': StepDef('F2L', 'af2l', 'Advanced F2L'),
}

# Without Bluetooth the user declares the rating with a 1-4 key.
MANUAL_RATING_KEYS: Final[dict[str, Rating]] = {
    '1': Rating.Again,
    '2': Rating.Hard,
    '3': Rating.Good,
    '4': Rating.Easy,
}

# Speed trend of a case: current Ao5 compared to the best Ao12 ever
# achieved (peak sustained performance). Display only, never feeds the
# FSRS rating or scheduling.
TREND_MIN_TIMINGS: Final[int] = 12
TREND_AT_PEAK: Final[float] = 1.10
TREND_DEGRADED: Final[float] = 1.30


class Trainer(SolveInterface):  # noqa: PLR0904
    """
    Training interface for practicing specific CFOP cases.

    Generates targeted scrambles for practicing cross, F2L, OLL, or PLL
    cases with optional solution hints.
    """

    def __init__(  # noqa: PLR0913
            self,
            *,
            step: str,
            case_codes: list[str],
            oldest: int,
            slowest: int,
            random: int,
            new_cases_limit: int,
            filters: list[str],
            free_play: bool,
            show_solution: bool,
            show_cube: bool,
            orientation: CubeOrientation,
            metronome: float,
            rng: Random,
    ) -> None:
        """Initialize trainer with step configuration and display options."""
        super().__init__()

        self.set_state('configure')

        self.method = 'CFOP'
        self.step = step
        self.step_config = STEP_CONFIGS[step]
        self.step_label = f'{ self.method }/{ self.step_config.display_name }'

        self.free_play = free_play
        self.show_solution = show_solution
        self.show_cube = show_cube
        self.metronome = metronome
        self.case_codes = case_codes
        self.oldest = oldest
        self.slowest = slowest
        self.filters = [f.lower() for f in filters]
        self.rng = rng
        self.orientation_faces = orientation
        self.random = random
        self.new_cases_limit = new_cases_limit

        self.trainings = load_trainings(self.method, self.step.upper())

        self.total_cases: int = 0
        self.filtered_cases: int = 0
        self.cases = self.get_cases()
        self.fsrs_probabilities = {
            tc.case.code: tc.case.probability for tc in self.cases
        }
        self.counter = 1
        self.session_data: list[tuple[str, Case, int]] = []

        self.fsrs_update = (
            TRAINER_FSRS
            and self.step_config.training_case is None
            and not self.free_play
        )
        self.fsrs_selection = (
            self.fsrs_update
            and not self.case_codes
            and not self.random
        )
        self.fsrs_scheduler = FSRSScheduler() if self.fsrs_update else None
        self.fsrs_rater = PerformanceRater() if self.fsrs_update else None
        self.fsrs_pending_rating: RatingBreakdown | None = None
        self.fsrs_pending_card: Card | None = None
        self.pending_previous_date: int | None = None
        self.fsrs_reference_solution: Algorithm = Algorithm()
        self.fsrs_last_focus: str | None = None
        self.fsrs_new_cases_introduced: int = 0

    def select_oldest_cases(
            self,
            valid_cases: dict[str, Case],
            count: int,
    ) -> list[str]:
        """
        Select cases by least recent practice date.

        Cases with no training data are prioritized as most urgent.

        Args:
            valid_cases: Dictionary of valid cases for the step
            count: Number of cases to select

        Returns:
            List of case codes sorted by practice urgency

        """
        case_dates: list[tuple[str, int]] = []

        for case_code in valid_cases:
            if case_code in self.trainings.cases:
                case_dates.append(
                    (
                        case_code,
                        self.trainings.cases[case_code].last_date,
                    ),
                )
            else:
                case_dates.append((case_code, 0))

        sorted_cases = sorted(case_dates, key=itemgetter(1))

        return [code for code, _ in sorted_cases[:count]]

    def select_slowest_cases(
            self,
            valid_cases: dict[str, Case],
            count: int,
    ) -> list[str]:
        """
        Select cases with worst average of 12.

        Cases with fewer than 12 attempts are prioritized as needing
        more practice.

        Args:
            valid_cases: Dictionary of valid cases for the step
            count: Number of cases to select

        Returns:
            List of case codes sorted by performance need

        """
        case_ao12s: list[tuple[str, int, bool]] = []

        for case_code in valid_cases:
            if case_code in self.trainings.cases:
                case_training = self.trainings.cases[case_code]
                stats = Statistics(case_training.timings)
                ao12 = stats.ao12
                has_enough = len(case_training.timings) >= 12

                if ao12 == -1:
                    case_ao12s.append((case_code, 999_999_999, False))
                else:
                    case_ao12s.append((case_code, ao12, has_enough))
            else:
                case_ao12s.append((case_code, 999_999_999, False))

        sorted_cases = sorted(
            case_ao12s,
            key=lambda x: (x[2], -x[1]),
        )

        return [code for code, _, _ in sorted_cases[:count]]

    def select_random_cases(
            self,
            valid_cases: dict[str, Case],
            count: int,
    ) -> list[str]:
        """
        Select cases randomly.

        Args:
            valid_cases: Dictionary of valid cases for the step
            count: Number of cases to select

        Returns:
            List of randomly selected case codes

        """
        codes = list(valid_cases.keys())
        self.rng.shuffle(codes)
        return codes[:count]

    def get_cases(self) -> list[TrainingCase]:
        """
        Build list of trained cases.

        Returns:
            List of validated cases to use in training.

        Raises:
            InvalidCaseError: If selected case is not valid for the step.

        """
        if self.step_config.training_case is not None:
            return [self.step_config.training_case]

        cases = get_collection(f'{ self.method }/{ self.step }').cases
        valid_cases: dict[str, Case] = {
            v.code: v for v in cases.values()
            if v.setup_algorithms
        }
        self.total_cases = len(valid_cases)

        if self.filters:
            valid_cases = {
                code: case for code, case in valid_cases.items()
                if (case.family or '').lower() in self.filters
                or any(g.lower() in self.filters for g in (case.groups or []))
            }
        self.filtered_cases = len(valid_cases)

        case_codes = self.case_codes or list(valid_cases.keys())

        if self.oldest > 0:
            case_codes = self.select_oldest_cases(
                valid_cases,
                self.oldest,
            )
        elif self.slowest > 0:
            case_codes = self.select_slowest_cases(
                valid_cases,
                self.slowest,
            )
        elif self.random != 0:
            count = (
                len(valid_cases) if self.random == -1 else self.random
            )
            case_codes = self.select_random_cases(valid_cases, count)

        def setup_sorter(algorithm: Algorithm) -> tuple[float, float]:
            ergonomics = algorithm.ergonomics
            return (
                ergonomics.estimated_execution_time,
                -ergonomics.ergonomic_score,
            )

        selected_cases = []
        for case_code in case_codes:
            if case_code not in valid_cases:
                error_string = (
                    f'Invalid case "{ case_code }" for { self.step_label }: '
                    'Case is unknown.'
                )
                raise InvalidCaseError(error_string)
            valid_case = valid_cases[case_code]

            setups = [
                setup
                for setup in valid_case.setup_algorithms
                if not setup.has_internal_rotations and not setup.has_rotations
            ]

            if not setups:
                error_string = (
                    f'Invalid case "{ case_code }" for { self.step_label }: '
                    'No available setup algorithm.'
                )
                raise InvalidCaseError(error_string)

            best_setups = sorted(
                setups,
                key=setup_sorter,
                reverse=False,
            )[:5]

            solution = self.resolve_solution(valid_case)

            selected_cases.append(
                TrainingCase(valid_case, best_setups, solution),
            )

        return selected_cases

    def resolve_solution(self, case: Case) -> Algorithm:
        """
        Resolve the solution to train for a case.

        A user can store a preferred solution per case in the training
        file under the ``solution`` key. When present, it is parsed and
        used as-is, with no verification that it solves the case or that
        it is a valid algorithm; an invalid value is the user's
        responsibility.

        Returns:
            The custom solution when one is defined, otherwise the
            cubing_algs main algorithm of the case.

        """
        case_training = self.trainings.cases.get(case.code)
        if case_training is not None and case_training.solution:
            return parse_moves(
                case_training.solution,
                trust_input=True,
            )

        return case.main_algorithm

    @property
    def bluetooth_scramble_is_completed(self) -> bool:
        """
        Check if training step is completed.

        Returns:
            True if the step is solved, False otherwise.

        """
        cube = VCube(
            self.bluetooth_cube_state,
            size=DEFAULT_CUBE_SIZE,
            check=False,
        )

        orientation_moves = ORIENTATION_FACE_MOVES[self.orientation_faces]
        if orientation_moves:
            cube.rotate(orientation_moves)

        return FaceletAnalyser().check_step(
            self.step_config.step_code,
            cube.state,
            self.orientation_faces,
        )

    def trainer_line(self) -> None:
        """Display training summary."""
        if self.step_config.training_case is not None:
            self.console.print(
                f'Training on { self.step_label }',
                style='trainer',
            )
            return

        n = len(self.cases)
        plural = 's' if n > 1 else ''
        label = self.step_label
        has_filter = bool(self.filters)

        if has_filter:
            filter_label = ' & '.join(self.filters)
            filter_plural = 's' if len(self.filters) > 1 else ''
            suffix = (
                f' ({ filter_label }'
                f' filter{ filter_plural },'
                f' { self.filtered_cases } matching,'
                f' { self.total_cases } total)'
            )
        else:
            suffix = f' ({ self.total_cases } total)'

        if self.case_codes:
            msg = (
                f'Training on { n } selected case{ plural } on { label }'
            )
        elif self.oldest > 0:
            msg = (
                f'Training on the { n } least practiced'
                f' case{ plural } on { label }{ suffix }'
            )
        elif self.slowest > 0:
            msg = (
                f'Training on the { n } slowest'
                f' case{ plural } on { label }{ suffix }'
            )
        elif self.random == -1:
            msg = (
                f'Training on all { n } case{ plural } on { label }'
                f' in random order{ suffix if has_filter else "" }'
            )
        elif self.random > 0:
            msg = (
                f'Training on { n } randomly selected'
                f' case{ plural } on { label }{ suffix }'
            )
        elif self.fsrs_selection:
            msg = (
                f'Training on all { n } case{ plural } on { label }'
                f' with spaced repetition{ suffix if has_filter else "" }'
            )
        else:
            msg = (
                f'Training on all { n } case{ plural } on { label }'
                f'{ suffix if has_filter else "" }'
            )

        if self.free_play:
            msg += ' (free play)'

        self.console.print(msg, style='trainer')

    def list_cases(self) -> None:
        """Display a table of all available cases with their training stats."""
        if self.step_config.training_case is not None:
            valid_cases = {tc.case.code: tc.case for tc in self.cases}
        else:
            collection = get_collection(f'{ self.method }/{ self.step }').cases
            valid_cases = {
                v.code: v for v in collection.values() if v.setup_algorithms
            }

        show_fsrs = self.step_config.training_case is None
        no_ao = '[no-ao]N/A[/no-ao]'

        table = Table(
            title=f'{ self.step_label } stats',
            box=box.SIMPLE,
            pad_edge=False,
        )
        table.add_column('Case', width=35)
        table.add_column('Σ', width=3, justify='right')
        table.add_column('Last date', width=10, justify='right')
        table.add_column('Best', width=5, justify='right')
        table.add_column('Ao5', width=7, justify='right')
        table.add_column('Ao12', width=5, justify='right')
        if show_fsrs:
            table.add_column('State', width=8, justify='right')
            table.add_column('Due', width=10, justify='right')

        for code, case in sorted(valid_cases.items()):
            link = format_term_timer_case_url(case)
            if link:
                head = (
                    f'[localhost][link={ link }]{ case.pretty_name }'
                    '[/link][/localhost]'
                )
            else:
                head = case.pretty_name
            case_training = self.trainings.cases.get(code)
            timing_cells = self.timing_cells(case_training, no_ao)
            row = [head, *timing_cells]
            if show_fsrs:
                row += self.fsrs_cells(case_training)
            table.add_row(*row)

        self.console.print(table)

    @staticmethod
    def speed_trend(stats: Statistics) -> str:
        """
        Format the speed trend of a case against its peak performance.

        Compares the current Ao5 to the best Ao12 ever achieved: at or
        near the peak the case is progressing or holding its best level,
        well above it the muscle memory is degrading. Display only,
        never feeds the FSRS rating or scheduling.

        Returns:
            Rich-formatted trend marker, or empty string when fewer
            than TREND_MIN_TIMINGS timings are available.

        """
        if len(stats.stack_time) < TREND_MIN_TIMINGS:
            return ''

        ao5 = stats.ao5
        peak = stats.best_ao12
        if ao5 <= 0 or peak <= 0:
            return ''

        ratio = ao5 / peak
        if ratio <= TREND_AT_PEAK:
            return '[trend-up]↗[/trend-up]'
        if ratio >= TREND_DEGRADED:
            return (
                f'[trend-down]↘ +{ (ratio - 1) * 100:.0f}%[/trend-down]'
            )
        return '[trend-flat]→[/trend-flat]'

    @staticmethod
    def timing_cells(
            case_training: 'CaseTraining | None',
            no_ao: str,
    ) -> list[str]:
        """
        Build the timing stat cells for a list_cases table row.

        Returns:
            List of [count, last_date, best, ao5, ao12, trend] Rich
            strings.

        """
        if case_training is None:
            return ['[stats]0[/stats]', no_ao, no_ao, no_ao, no_ao]

        count = len(case_training.timings)
        timings = [t * MS_TO_NS_FACTOR for t in case_training.timings]
        stats = Statistics(timings)
        last_date = datetime.fromtimestamp(
            case_training.last_date, tz=UTC,
        ).astimezone().strftime('%Y-%m-%d')

        best_str = (
            f'[duration]{ format_duration(stats.best) }[/duration]'
            if count else no_ao
        )
        trend_str = Trainer.speed_trend(stats)
        if '↘' in trend_str:
            trend_str = '[trend-down]↘[/trend-down]'
        if count < 5:
            ao5_str = no_ao
        elif trend_str:
            ao5_str = (
                f'[ao5]{ format_duration(stats.ao5) }[/ao5] { trend_str }'
            )
        else:
            ao5_str = f'[ao5]{ format_duration(stats.ao5) }[/ao5]'
        ao12_str = (
            f'[ao12]{ format_duration(stats.ao12) }[/ao12]'
            if count >= 12 else no_ao
        )
        return [
            f'[stats]{ count }[/stats]', last_date, best_str, ao5_str,
            ao12_str,
        ]

    @staticmethod
    def fsrs_cells(case_training: 'CaseTraining | None') -> list[str]:
        """
        Build the FSRS state and due-date cells for a list_cases table row.

        Returns:
            List of [state, due] Rich strings.

        """
        card = case_training.fsrs_card if case_training else None

        return [format_fsrs_state(card), format_fsrs_due(card)]

    @property
    def fsrs_new_cases_remaining(self) -> int:
        """
        Remaining session budget for introducing new cases.

        Returns:
            Number of new cases the session may still introduce.

        """
        return max(0, self.new_cases_limit - self.fsrs_new_cases_introduced)

    def fsrs_track_new_case(
            self,
            case_code: str,
            *,
            was_new_case: bool,
    ) -> None:
        """
        Consume session budget once a new case has an FSRS card.

        A new case only counts as introduced when the save actually
        created its card: a discarded rep or a skipped FSRS update
        (manual mode, non-rating key) leaves the case new for the
        scheduler and must not consume the budget.
        """
        if not was_new_case:
            return
        case_training = self.trainings.cases.get(case_code)
        if case_training is not None and case_training.fsrs_card is not None:
            self.fsrs_new_cases_introduced += 1

    @property
    def fsrs_manual_rating(self) -> bool:
        """
        Whether FSRS ratings are collected at the keyboard.

        Returns:
            True when ratings must be entered manually with the 1-4 keys.

        """
        return self.fsrs_update and (
            self.bluetooth_interface is None
            or TRAINER_FSRS_RATING == 'manual'
        )

    @property
    def fsrs_cards(self) -> 'dict[str, Card]':
        """
        FSRS cards of the trained cases restricted to the selected pool.

        Cards for cases outside the active pool (e.g. excluded by
        ``--oldest``, ``--slowest`` or ``--filter``) are dropped so the
        focus, mastery and case selection all reason about the same set
        of cases the session can actually serve.

        Returns:
            FSRS cards keyed by case code, only for in-pool seen cases.

        """
        return {
            code: ct.fsrs_card
            for code, ct in self.trainings.cases.items()
            if ct.fsrs_card is not None
            and code in self.fsrs_probabilities
        }

    def fsrs_focus_line(self) -> None:
        """Display FSRS session focus and mastery stats if they changed."""
        if not self.fsrs_selection:
            return

        cards = self.fsrs_cards
        focus = FSRSScheduler.compute_session_focus(
            cards, self.fsrs_probabilities, self.fsrs_new_cases_remaining,
        )
        mastered, total = FSRSScheduler.compute_mastery(
            cards, self.fsrs_probabilities,
        )
        mastery_str = (
            f'{ mastered }/{ total } mastered' if mastered > 0 else ''
        )
        focus_str = f'{ focus } { mastery_str }'.strip()

        if (
                self.fsrs_last_focus is not None
                and focus_str[:6] == self.fsrs_last_focus[:6]
        ):
            return

        self.fsrs_last_focus = focus_str

        mc = 10 + len(str(self.counter))

        self.console.print(
            f'[fsrs-focus]{ "Practicing".ljust(mc) }:[/fsrs-focus] '
            f'[context]{ focus_str }[/context]',
        )

    def fsrs_case_line(self, selected_case: Case) -> None:  # noqa: PLR0914
        """Display FSRS card state, metrics, due date and delta."""
        if not self.fsrs_update or self.fsrs_scheduler is None:
            return

        mc = 10 + len(str(self.counter))
        name = selected_case.name.center(mc)
        case_training = self.trainings.cases.get(selected_case.code)

        if case_training is None or case_training.fsrs_card is None:
            self.console.print(
                f'[fsrs-case]{ name }:[/fsrs-case] '
                '[new]New case evaluation[/new]',
            )
            return

        card = case_training.fsrs_card
        state_label, state_klass = fsrs_state_label(card)
        inner_scheduler = self.fsrs_scheduler.scheduler

        if card.step is not None:
            total_steps = (
                len(inner_scheduler.relearning_steps)
                if card.state.name == 'Relearning'
                else len(inner_scheduler.learning_steps)
            )
            state_str = (
                f'[{ state_klass }]{ state_label }'
                f' ({ card.step + 1 }/{ total_steps })'
                f'[/{ state_klass }]'
            )
        else:
            state_str = (
                f'[{ state_klass }]{ state_label }[/{ state_klass }]'
            )

        metrics_str = ''
        if card.stability is not None:
            metrics_str = (
                f' (S:{ card.stability:.1f}d '
                f'D:{ card.difficulty:.1f})'
            )

        due = card.due.astimezone()
        now = datetime.now(UTC).astimezone()
        delta_days = (due.date() - now.date()).days

        if delta_days < 0:
            n = abs(delta_days)
            s = 's' if n > 1 else ''
            delta_str = f'{ n } day{ s } ago'
            due_str = f' [warning]overdue { delta_str }[/warning]'

        elif delta_days == 0:
            delta_minutes = int((due - now).total_seconds() / 60)
            if delta_minutes > 0:
                h, m = divmod(
                    math.ceil((due - now).total_seconds() / 60), 60,
                )
                hm = f'{ h } hours' if h > 0 else f'{ m } minutes'
                due_str = f' in { hm }'
            elif delta_minutes < 0:
                h, m = divmod(
                    math.ceil((now - due).total_seconds() / 60), 60,
                )
                hm = f'{ h } hours' if h > 0 else f'{ m } minutes'
                due_str = f' [caution]overdue { hm } ago[/caution]'
            else:
                due_str = ' [caution]due now[/caution]'

        else:
            due_str = (
                f' in { delta_days }'
                f' day{ "s" if delta_days > 1 else "" }'
            )

        self.console.print(
            f'[fsrs-case]{ name }:[/fsrs-case] '
            f'{ state_str }{ due_str }{ metrics_str }',
        )

    @staticmethod
    def format_score_bands(score: float, rating_klass: str) -> str:
        """
        Format the score positioned within a colored band scale.

        Returns a Rich-formatted string like:
            [dim]E<0.5<[/dim][good]G:0.73<1.0[/good][dim]<H<1.5<A[/dim]

        Returns:
            Rich-formatted band scale string with the current score embedded.

        """
        e = f'E<={BAND_EASY}'
        g = f'G<={BAND_GOOD}'
        h = f'H<={BAND_AGAIN}'
        a = 'A'
        bands = [
            (e, 'easy'),
            (g, 'good'),
            (h, 'hard'),
            (a, 'again'),
        ]
        if score <= BAND_EASY:
            active = 'easy'
        elif score <= BAND_GOOD:
            active = 'good'
        elif score <= BAND_AGAIN:
            active = 'hard'
        else:
            active = 'again'

        parts = []
        pre: list[str] = []
        post: list[str] = []
        found = False
        for label, klass in bands:
            if klass == active:
                found = True
                if label == a:
                    active_label = f'{label}:{score:.2f}'
                else:
                    active_label = label.replace('<', f':{score:.2f}<', 1)
                parts.append(f'[{rating_klass}]{active_label}[/{rating_klass}]')
            elif not found:
                pre.append(label)
            else:
                post.append(label)

        result = ''
        if pre:
            result += f'[dim]{"<".join(pre)}<[/dim]'
        result += parts[0]
        if post:
            result += f'[dim]<{"<".join(post)}[/dim]'
        return result

    @staticmethod
    def format_penalty_cell(value: float) -> str:
        """
        Format a score penalty contribution, dimmed when null.

        Returns:
            Rich-formatted signed penalty string.

        """
        if value > 0:
            return f'[caution]+{ value:.2f}[/caution]'
        return f'[no-ao]+{ value:.2f}[/no-ao]'

    @staticmethod
    def format_breakdown_lines(
            breakdown: RatingBreakdown,
            rating_klass: str,
    ) -> list[str]:
        """
        Format the debug lines detailing a FSRS rating breakdown.

        One line per criterion showing the raw value, the reference it
        is compared against, and its exact contribution to the final
        score, followed by the score line positioned in the bands and
        the categorical overrides (HTM forcing, high-stability floor)
        when they fired.

        Returns:
            List of Rich-formatted debug lines.

        """
        cell = Trainer.format_penalty_cell
        rows = [
            (
                'tps',
                f'{ breakdown.tps:.2f}',
                f'ref { breakdown.tps_ref }, /{ TPS_SCALE }',
                cell(breakdown.tps_pen),
            ),
            (
                'pauses',
                str(breakdown.pauses),
                f'free { PAUSE_TOLERANCE }, x{ PAUSE_WEIGHT }',
                cell(breakdown.pause_pen),
            ),
            (
                'missed',
                str(breakdown.missed_qtm),
                f'x{ MISSED_WEIGHT }',
                cell(breakdown.missed_pen),
            ),
            (
                'time',
                f'{ breakdown.time_s:.2f}s',
                f'soft { breakdown.time_soft }s, /{ TIME_SCALE }',
                cell(breakdown.time_pen),
            ),
        ]

        if breakdown.forced:
            forcing_impact = '[again]over solution -> Again[/again]'
        else:
            forcing_impact = '[no-ao]within solution[/no-ao]'
        rows.append(
            (
                'qtm',
                str(breakdown.executed_qtm),
                f'solution { breakdown.reference_qtm }',
                forcing_impact,
            ),
        )

        lines = [
            f'  [consign]{ label:<7}[/consign]'
            f'{ value:<7}'
            f'[no-ao]{ f"({ ref })":<20}[/no-ao]'
            f'{ impact }'
            for label, value, ref, impact in rows
        ]

        bands = Trainer.format_score_bands(breakdown.score, rating_klass)
        score_line = (
            f'  [consign]score  [/consign]'
            f'{ breakdown.score:<7.2f}'
            f'{ bands }'
        )
        if breakdown.floored:
            score_line += (
                ' [hard]floored Again -> Hard'
                f' (S >= { HIGH_STABILITY_FLOOR_DAYS:.0f}d, clean)[/hard]'
            )
        lines.append(score_line)

        return lines

    @staticmethod
    def format_card_change(
            current_card: 'Card | None',
            preview_card: 'Card',
    ) -> str:
        """
        Format state transition and metric deltas for FSRS preview.

        Returns:
            Rich-formatted string with optional state change arrow and
            stability/difficulty values with signed deltas.

        """
        old_label, old_klass = (
            fsrs_state_label(current_card)
            if current_card is not None
            else ('New', 'new')
        )
        new_label, new_klass = fsrs_state_label(preview_card)
        if old_label != new_label:
            state_str = (
                f' [{ old_klass }]{ old_label }[/{ old_klass }]'
                f' -> [{ new_klass }]{ new_label }[/{ new_klass }]'
            )
        else:
            state_str = ''

        new_s = preview_card.stability
        new_d = preview_card.difficulty
        if new_s is None or new_d is None:
            return state_str

        if (
            current_card is not None
            and current_card.stability is not None
            and current_card.difficulty is not None
        ):
            ds = new_s - current_card.stability
            dd = new_d - current_card.difficulty
            s_style = 'green' if ds > 0 else 'red'
            d_style = 'red' if dd > 0 else 'green'
            s_delta = (
                (
                    f' [{ s_style }]{ "+" if ds > 0 else "" }'
                    f'{ ds:.1f}[/{ s_style }]'
                )
                if round(ds, 1) != 0 else ''
            )
            d_delta = (
                (
                    f' [{ d_style }]{ "+" if dd > 0 else "" }'
                    f'{ dd:.1f}[/{ d_style }]'
                )
                if round(dd, 1) != 0 else ''
            )
        else:
            s_delta = d_delta = ''

        metrics_str = (
            f' (S:{ new_s:.1f}d{ s_delta } D:{ new_d:.1f}{ d_delta })'
        )
        return state_str + metrics_str

    def fsrs_result_line(
            self,
            selected_case: Case,
            rating: Rating,
            old_card: 'Card | None',
            new_card: 'Card',
            breakdown: RatingBreakdown | None = None,
    ) -> None:
        """Display FSRS card evolution after a rating is applied."""
        due = new_card.due.astimezone()
        now = datetime.now(UTC).astimezone()
        delta_days = (due.date() - now.date()).days

        if delta_days == 0:
            delta_minutes = int((due - now).total_seconds() / 60)
            if delta_minutes > 0:
                mins = math.ceil((due - now).total_seconds() / 60)
                due_str = f'in { mins } minutes'
            else:
                due_str = '[caution]due now[/caution]'
        else:
            due_str = f'in { delta_days } day{ "s" if delta_days > 1 else "" }'

        card_change_str = self.format_card_change(old_card, new_card)
        rating_klass = rating.name.lower()

        suffix = ''
        if DEBUG and breakdown is not None:
            suffix = '\n' + '\n'.join(
                self.format_breakdown_lines(breakdown, rating_klass),
            )

        mc = 10 + len(str(self.counter))
        name = selected_case.name.center(mc)

        self.console.print(
            f'[fsrs-result]{ name }:[/fsrs-result] '
            f'[{ rating_klass }]{ rating.name }[/{ rating_klass }],'
            f'{ card_change_str } review { due_str }{ suffix }',
        )

    def fsrs_preview_line(self, solve: Solve, selected_case: Case) -> None:
        """Compute and display FSRS rating preview before the save prompt."""
        if self.fsrs_rater is None or self.fsrs_scheduler is None:
            return

        if not solve.advanced:
            # No execution data: the rating is collected manually, there is
            # nothing to preview.
            return

        current_card = (
            self.trainings.cases[selected_case.code].fsrs_card
            if selected_case.code in self.trainings.cases
            else None
        )
        stability = current_card.stability if current_card is not None else None

        breakdown = self.fsrs_rater.rate_with_details(
            solve, self.step, self.fsrs_reference_solution, stability,
        )
        self.fsrs_pending_rating = breakdown
        preview_card = self.fsrs_scheduler.update_card(
            current_card,
            breakdown.rating,
        )
        self.fsrs_pending_card = preview_card
        self.fsrs_result_line(
            selected_case,
            breakdown.rating,
            current_card,
            preview_card,
            breakdown,
        )

    def fsrs_dnf_preview_line(self, selected_case: Case) -> None:
        """Display the Again rating applied when saving a DNF attempt."""
        if self.fsrs_scheduler is None:
            return

        current_card = (
            self.trainings.cases[selected_case.code].fsrs_card
            if selected_case.code in self.trainings.cases
            else None
        )
        preview_card = self.fsrs_scheduler.update_card(
            current_card,
            Rating.Again,
        )
        self.fsrs_pending_card = preview_card
        self.fsrs_result_line(
            selected_case,
            Rating.Again,
            current_card,
            preview_card,
        )

    def case_in_learning_phase(self, selected_case: Case) -> bool:
        """
        Check whether the FSRS card of a case is in a learning phase.

        A case is in a learning phase when its card is in the Learning
        or Relearning state. Cases never trained have no card yet and
        are deliberately excluded: the first attempt acts as an
        unbiased probe of prior knowledge.

        Returns:
            True when the card exists and is Learning or Relearning.

        """
        if not self.fsrs_update:
            return False

        case_training = self.trainings.cases.get(selected_case.code)
        if case_training is None or case_training.fsrs_card is None:
            return False

        return case_training.fsrs_card.state in {
            State.Learning,
            State.Relearning,
        }

    def compute_pre_aufs(self, solution: Algorithm) -> Move | None:
        """
        Find the pre-AUF that lets the solution complete the step.

        Tries each U-face rotation before the solution and returns the
        first one that solves the training step from the scrambled state.

        Returns:
            The pre-AUF move, or None when no rotation is needed.

        """
        cube = VCube(size=DEFAULT_CUBE_SIZE)
        cube.rotate(self.scramble_oriented)

        fa = FaceletAnalyser()

        for rotation in ['', 'U', "U'", 'U2']:
            cube_copy = cube.copy()
            cube_copy.rotate(rotation)
            cube_copy.rotate(solution)

            if fa.check_step(self.step_config.step_code, cube_copy.state):
                return Move(rotation) if rotation else None

        return None

    def build_reference_solution(self, solution: Algorithm) -> Algorithm:
        """
        Build the reference solution for this attempt, with pre-AUF.

        Returns a new Algorithm (the original is left untouched) made of the
        computed pre-AUF followed by the solution, so it matches what the cube
        must actually perform from the scrambled state. This is the reference
        the FSRS rater compares the execution against to detect forcing.

        Returns:
            The pre-AUF merged into the solution, or the solution unchanged
            when no pre-AUF is needed, or an empty Algorithm when no solution
            is available.

        """
        if not solution:
            return Algorithm()

        pre_auf = self.compute_pre_aufs(solution)
        if pre_auf is None:
            return solution

        merged_head = compress_moves(Algorithm([pre_auf, solution[0]]))
        return Algorithm([*merged_head, *solution[1:]])

    def start_line(
            self,
            cube: VCube,
            selected_case: Case,
            solution: Algorithm,
    ) -> None:
        """Display training case, scramble, and optional solution."""
        self.fsrs_focus_line()
        self.fsrs_case_line(selected_case)

        link = format_term_timer_case_url(selected_case)
        name = selected_case.pretty_name

        if self.show_cube:
            print_cube_trainer(
                cube,
                self.orientation_faces,
                self.step_config.printer_mode,
            )

        scramble_line = f'[moves]{ self.scramble_oriented }[/moves]'
        if self.cube_orientation_moves:
            scramble_line = (
                f'[rotation]{ self.cube_orientation_moves }[/rotation] '
                + scramble_line
            )

        attempt = 1
        if selected_case.code in self.trainings.cases:
            attempt = len(self.trainings.cases[selected_case.code].timings) + 1

        if solution and (
                self.show_solution
                or self.case_in_learning_phase(selected_case)
        ):
            formatted_algorithm = format_alg_triggers(
                format_alg_moves(
                    format_alg_aufs(
                        str(solution),
                        pre_auf=True,
                        post_auf=True,
                    ),
                ),
                DEFAULT_TRIGGERS,
            )

            self.console.print(
                f'[solution]Solution #{ self.counter }:[/solution]',
                f'[moves]{ formatted_algorithm }[/moves]',
            )

        self.console.print(
            f'[scramble]Training #{ self.counter }:[/scramble]',
            scramble_line,
            f'[comment]// [link={ link }]{ name }[/link] '
            f'#{ attempt }[/comment]',
        )

        if self.bluetooth_interface:
            self.console.print(
                'Apply the scramble on the cube to init the timer,',
                '[key](q)[/key] to quit.',
                style='consign',
                end='',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer,',
                '[key](q)[/key] to quit.',
                style='consign',
                end='',
            )

    def save_line(
            self,
            *,
            manual_rating: bool = False,
            dnf: bool = False,
    ) -> None:
        """Display instructions for saving or canceling the solve."""
        if dnf:
            self.console.print(
                'Press any key to rate [again]Again[/again] and continue,',
                '[key](z)[/key] discard,',
                '[key](k)[/key] quit,',
                '[key](q)[/key] rate & quit.',
                style='consign',
                end='',
            )
            return

        if manual_rating:
            self.console.print(
                'Rate:',
                '[key](1)[/key] Again,',
                '[key](2)[/key] Hard,',
                '[key](3)[/key] Good,',
                '[key](4)[/key] Easy,',
                '[key](z)[/key] discard,',
                '[key](k)[/key] quit,',
                '[key](q)[/key] save & quit.',
                style='consign',
                end='',
            )
            return

        if self.fsrs_update:
            self.console.print(
                'Press any key to save and continue,',
                '[key](1-4)[/key] override rating,',
                '[key](z)[/key] discard,',
                '[key](k)[/key] quit,',
                '[key](q)[/key] save & quit.',
                style='consign',
                end='',
            )
            return

        self.console.print(
            'Press any key to save and continue,',
            '[key](z)[/key] discard,',
            '[key](k)[/key] quit,',
            '[key](q)[/key] save & quit.',
            style='consign',
            end='',
        )

    @staticmethod
    def solve_stats_line(solve: Solve) -> str:
        """
        Format the stats summary line for training mode display.

        Returns:
            Rich-formatted string with HTM, TPS, fluency, missed moves,
            pauses, and rotations, or empty string if no advanced data.

        """
        if not solve.advanced:
            return ''

        htm = solve.reconstruction.metrics.htm
        metric_string = f'[htm]{ htm } HTM[/htm] '

        missed_line = ''
        if solve.all_missed_moves:
            missed_line = (
                '[exec-overhead]'
                f'{ solve.all_missed_moves } missed QTM'
                '[/exec-overhead] '
            )

        pause_line = ''
        if solve.execution_pauses:
            pause_line = (
                f'[caution]{ solve.execution_pauses } Pauses[/caution]'
            )

        rotation_line = ''
        if solve.rotations:
            rotation_line = (
                f' [caution]{ solve.rotations } Rotations[/caution]'
            )

        fluency_line = ''
        if solve.fluency > 0:
            fluency_line = f'{ format_fluency(solve.fluency) } '

        return (
            f'{ metric_string }'
            f'[tps]{ solve.tps:.2f} TPS[/tps] '
            f'{ fluency_line }{ missed_line }{ pause_line }{ rotation_line }'
        )

    @staticmethod
    def solve_algo_line(solve: Solve, step: StepSummary) -> str:
        """
        Format the algorithm line for a single step with AUF and oHTM.

        Returns:
            Rich-formatted string with executed moves and a comment showing
            AUF counts and oHTM overhead, or empty string if unavailable.

        """
        aufs = ''
        if step['aufs'][0]:
            aufs += f' +{ step["aufs"][0] } pre-AUF'
        if step['aufs'][1]:
            aufs += f' +{ step["aufs"][1] } post-AUF'

        optimal = ''
        if step['case']:
            step_code = step['name'].split(' ')[0]
            step_case = get_case(step_code, step['case'])
            optimal_htm = step_case.optimal_htm
            if optimal_htm:
                delta_htm = step['moves_prettified'].transform(
                    remove_auf_moves,
                ).metrics.htm - optimal_htm
                if delta_htm > 0:
                    optimal = f' +{ delta_htm } oHTM'

        comment = ''
        if aufs or optimal:
            comment = f' [comment]//{ aufs }{ optimal }[/comment]'

        algo_str = solve.reconstruction_step_line(step, multiple=True)
        return f'[consign]{ algo_str }[/consign]{ comment }'

    @staticmethod
    def solve_algo_lines(solve: Solve, indent_width: int = 0) -> list[str]:
        """
        Format algorithm lines for all steps with moves.

        For multi-step solves, each line is prefixed with the step name
        left-aligned and padded to indent_width so moves stay aligned.
        For single-step solves, lines have no prefix.

        Returns:
            List of Rich-formatted strings, one per step with moves.

        """
        if not solve.method_applied:
            return []

        steps = [s for s in solve.method_applied.summary if s['moves']]
        if not steps:
            return []

        multi = len(steps) > 1
        lines = []

        for step in steps:
            line = Trainer.solve_algo_line(solve, step)
            if not line:
                continue
            if multi:
                step_name = step['name'].split(' ')[0]
                padding = ' ' * (indent_width - len(step_name) - 1)
                line = f'[step]{ step_name }:[/step]{ padding }{ line }'
            else:
                line = ' ' * indent_width + line
            lines.append(line)

        return lines

    def solve_line(self, solve: Solve, selected_case: Case) -> None:
        """Display training solve results and execution details."""
        self.pending_previous_date = self.trainings.add_timing(
            selected_case.code,
            int(self.elapsed_time / MS_TO_NS_FACTOR),
            int(self.date),
        )

        timings = [
            i * MS_TO_NS_FACTOR
            for i in self.trainings.cases[selected_case.code].timings
        ]
        old_stats = Statistics(timings[:-1])
        new_stats = Statistics(timings)

        if solve.flag == DNF:
            SOUND_PLAYER.solve_failed()
        else:
            SOUND_PLAYER.solve_step()

        self.clear_line(full=True)

        if solve.method_applied:
            indent_width = len(f'Executed #{ self.counter }: ')
            self.console.print(
                f'[analysis]Executed #{ self.counter }:[/analysis]',
                self.solve_stats_line(solve),
            )
            for algo_line in self.solve_algo_lines(solve, indent_width):
                self.console.print(algo_line)

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            self.format_series_line(
                new_stats, STATS_LIVE_SERIES,
                suffix=self.speed_trend(new_stats),
            ),
        )

        if new_stats.total > 1 and new_stats.best < old_stats.best:
            mc = 9 + len(str(self.counter))
            self.console.print(
                f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
                f'[best]{ format_time(new_stats.best) }[/best]',
                format_delta(new_stats.best - old_stats.best),
            )

        self.print_session_records(
            new_stats, old_stats, STATS_SESSION_SERIES,
        )

    def dnf_line(self) -> None:
        """Display a DNF training attempt; its timing is never recorded."""
        SOUND_PLAYER.solve_failed()

        self.clear_line(full=True)

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            '[dnf]DNF[/dnf]',
        )

    def resolve_fsrs_rating(
            self,
            solve: Solve,
            rater: PerformanceRater,
            old_card: 'Card | None',
            manual_rating: Rating | None,
            *,
            dnf: bool,
    ) -> Rating:
        """
        Resolve the FSRS rating to apply for a saved attempt.

        Returns:
            The manual override when given, Again for a DNF, the
            pending previewed rating, or a freshly computed rating.

        """
        if manual_rating is not None:
            return manual_rating
        if dnf:
            return Rating.Again
        pending = self.fsrs_pending_rating
        if pending is not None:
            return pending.rating
        return rater.rate(
            solve,
            self.step,
            self.fsrs_reference_solution,
            old_card.stability if old_card is not None else None,
        )

    async def save_training(  # noqa: C901, PLR0912
            self,
            selected_case: Case,
            solve: Solve,
            *,
            dnf: bool = False,
    ) -> bool:
        """
        Save the completed training with optional flag modifications.

        Waits for user input to mark the training with a flag (DNF) or
        cancel it. Persists the training to storage and displays confirmation.
        Handles both keyboard and bluetooth gesture input.

        DNF trainings never record a timing: saving one only applies an
        FSRS Again rating, which cannot be overridden.

        Returns:
            True if user quit (pressed 'q', 'k' or ESC), False otherwise.

        """
        self.set_state('saving')

        if self.bluetooth_interface:
            getch_task = asyncio.create_task(self.getch('save'))
            tasks = [
                getch_task,
                asyncio.create_task(self.save_gesture_event.wait()),
            ]
            await self.wait_control(tasks)

            char = ''
            if not self.save_gesture_event.is_set():
                result = getch_task.result()
                char = result if isinstance(result, str) else ''
            else:
                self.clear_line(full=True)
                char = self.save_gesture
        else:
            char = await self.getch('save')

        manual = self.fsrs_manual_rating
        manual_rating = (
            MANUAL_RATING_KEYS.get(char)
            if self.fsrs_update and not dnf
            else None
        )

        # Any key other than z/k saves; invalid keys in manual mode skip
        # FSRS. A DNF always rates Again.
        discard = char in {'z', 'k'}
        skip_fsrs = manual and manual_rating is None and not dnf

        save_string = ''
        if discard:
            if not dnf:
                self.trainings.pop_timing(
                    selected_case.code,
                    self.pending_previous_date,
                )
            SOUND_PLAYER.save_discarded()
            save_string = 'Training discarded'
        else:
            if (
                dnf
                and not skip_fsrs
                and self.fsrs_update
                and selected_case.code not in self.trainings.cases
            ):
                # DNF on a never-trained case: no timing is recorded,
                # create the entry so the FSRS card can be persisted.
                self.trainings.cases[selected_case.code] = CaseTraining(
                    code=selected_case.code,
                    last_date=int(self.date),
                    timings=[],
                )

            if (
                not skip_fsrs
                and self.fsrs_update
                and self.fsrs_scheduler is not None
                and self.fsrs_rater is not None
                and selected_case.code in self.trainings.cases
            ):
                case_training = self.trainings.cases[selected_case.code]
                old_card = case_training.fsrs_card
                rating = self.resolve_fsrs_rating(
                    solve,
                    self.fsrs_rater,
                    old_card,
                    manual_rating,
                    dnf=dnf,
                )
                pending = self.fsrs_pending_rating
                pending_card = self.fsrs_pending_card
                # Fuzz is redrawn at each review_card call: reuse the
                # previewed card when the applied rating is the previewed
                # one, so the saved due date matches the one displayed.
                # A DNF preview is always rated Again, like its save.
                if pending_card is not None and (
                    dnf
                    or (pending is not None and rating == pending.rating)
                ):
                    case_training.fsrs_card = pending_card
                else:
                    case_training.fsrs_card = self.fsrs_scheduler.update_card(
                        old_card,
                        rating,
                    )
                if manual_rating is not None:
                    self.fsrs_result_line(
                        selected_case,
                        rating,
                        old_card,
                        case_training.fsrs_card,
                    )

            save_trainings(self.trainings)
            SOUND_PLAYER.save_confirmed()
            if not dnf:
                self.session_data.append(
                    (
                        selected_case.code,
                        selected_case,
                        self.elapsed_time,
                    ),
                )

        if save_string:
            self.console.print(
                f'[duration]Duration #{ self.counter }:[/duration] '
                f'[warning]{ save_string }[/warning]',
            )

        return char in {'q', 'k', ESCAPE_CHAR}

    async def start(  # noqa: C901, PLR0911, PLR0912, PLR0915
            self,
    ) -> bool:
        """
        Execute training workflow for single case.

        Returns:
            True to continue training, False to quit.

        """
        self.init_solve()

        fsrs_selected: TrainingCase | None = None
        was_new_case = False
        if self.fsrs_selection and self.fsrs_scheduler is not None:
            cards = self.fsrs_cards
            chosen_code = self.fsrs_scheduler.select_next_case(
                cards,
                self.fsrs_probabilities,
                new_cases_limit=self.fsrs_new_cases_remaining,
            )
            was_new_case = chosen_code not in cards
            fsrs_selected = next(
                (tc for tc in self.cases if tc.case.code == chosen_code),
                None,
            )

        selected_case, self.scramble, solution = trainer(
            self.step,
            self.cases,
            self.rng,
            self.cube_orientation_moves,
            selected_case=fsrs_selected,
        )

        bt_scramble_done = (
            self.bluetooth_cube and self.bluetooth_scramble_is_completed
        )

        if bt_scramble_done:
            cube = VCube(
                self.bluetooth_cube_state,
                size=DEFAULT_CUBE_SIZE,
                check=False,
            )
        else:
            cube = VCube(size=DEFAULT_CUBE_SIZE)

        cube.rotate(self.scramble)
        self.facelets_scrambled = cube.state

        if self.bluetooth_cube and not bt_scramble_done:
            scramble = facelets_to_facelets_algorithm(
                self.bluetooth_cube_state,
                cube.state,
            )
            self.scramble_oriented = self.reorient(scramble)
        else:
            self.scramble_oriented = self.reorient(self.scramble)

        self.fsrs_reference_solution = self.build_reference_solution(solution)
        self.start_line(cube, selected_case, self.fsrs_reference_solution)

        quit_training = await self.scramble_solve()

        if quit_training is not None:
            return quit_training

        quit_training = await self.wait_solve()
        if quit_training:
            return False

        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        if (
                self.bluetooth_cube
                and not self.moves
                and not self.bluetooth_scramble_is_completed
        ):
            # Keyboard start/stop without any move on the connected
            # cube: a misfire, not an attempt, nothing to record.
            self.clear_line(full=True)
            return True

        flag: SolveFlag = ''
        if self.bluetooth_cube and not self.bluetooth_scramble_is_completed:
            flag = DNF

        moves = []
        if self.moves:
            first_time = self.moves[0]['time']
            for move in self.moves:
                timing = int((move['time'] - first_time) / MS_TO_NS_FACTOR)
                moves.append(f'{ move["move"] }@{ timing }')

        solve = Solve(
            self.date,
            self.elapsed_time,
            self.scramble,
            flag=flag,
            timer='Term-Timer',
            device=(
                self.bluetooth_interface
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.name
            ) or '',
            session='training',
            solve_id=self.counter,
            cube_size=DEFAULT_CUBE_SIZE,
            moves=' '.join(moves),
        )
        solve.method_name = self.method.lower()

        if flag == DNF:
            # A DNF never records a timing: saving only applies an FSRS
            # Again rating, which cannot be overridden.
            self.fsrs_pending_rating = None
            self.fsrs_pending_card = None
            self.dnf_line()

            if not self.free_play and self.fsrs_update:
                self.fsrs_dnf_preview_line(selected_case)
                self.save_line(dnf=True)

                quit_training = await self.save_training(
                    selected_case,
                    solve,
                    dnf=True,
                )

                self.fsrs_track_new_case(
                    selected_case.code,
                    was_new_case=was_new_case,
                )

                if quit_training:
                    return False

            self.counter += 1

            return True

        self.fsrs_pending_rating = None
        self.fsrs_pending_card = None
        self.solve_line(solve, selected_case)

        if not self.free_play:
            if self.fsrs_update:
                self.fsrs_preview_line(solve, selected_case)
            self.save_line(manual_rating=self.fsrs_manual_rating)

            quit_training = await self.save_training(selected_case, solve)

            self.fsrs_track_new_case(
                selected_case.code,
                was_new_case=was_new_case,
            )

            if quit_training:
                return False
        else:
            self.session_data.append(
                (
                    selected_case.code,
                    selected_case,
                    self.elapsed_time,
                ),
            )

        self.counter += 1

        return True
