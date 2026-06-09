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
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.vcube import VCube
from fsrs import Rating
from rich import box
from rich.table import Table

from term_timer.annotations import TrainingCase
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
from term_timer.formatter import format_term_timer_case_url
from term_timer.formatter import format_time
from term_timer.fsrs.rating import BAND_AGAIN
from term_timer.fsrs.rating import BAND_EASY
from term_timer.fsrs.rating import BAND_GOOD
from term_timer.fsrs.rating import PerformanceRater
from term_timer.fsrs.rating import RatingBreakdown
from term_timer.fsrs.scheduler import FSRSScheduler
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

    from term_timer.fsrs.storage import CaseTraining


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

            selected_cases.append(TrainingCase(valid_case, best_setups))

        return selected_cases

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

        table = Table(title=f'{ self.step_label } stats', box=box.SIMPLE)
        table.add_column('Case', width=35)
        table.add_column('Σ', width=3, justify='right')
        table.add_column('Last date', width=10, justify='right')
        table.add_column('Best', width=5, justify='right')
        table.add_column('Ao5', width=5, justify='right')
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
                row += self.fsrs_cells(case_training, no_ao)
            table.add_row(*row)

        self.console.print(table)

    @staticmethod
    def timing_cells(
            case_training: 'CaseTraining | None',
            no_ao: str,
    ) -> list[str]:
        """
        Build the timing stat cells for a list_cases table row.

        Returns:
            List of [count, last_date, best, ao5, ao12] Rich strings.

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
        ao5_str = (
            f'[ao5]{ format_duration(stats.ao5) }[/ao5]'
            if count >= 5 else no_ao
        )
        ao12_str = (
            f'[ao12]{ format_duration(stats.ao12) }[/ao12]'
            if count >= 12 else no_ao
        )
        return [
            f'[stats]{ count }[/stats]', last_date, best_str, ao5_str, ao12_str,
        ]

    @staticmethod
    def fsrs_cells(
            case_training: 'CaseTraining | None',
            no_ao: str,
    ) -> list[str]:
        """
        Build the FSRS state and due-date cells for a list_cases table row.

        Returns:
            List of [state, due] Rich strings.

        """
        if case_training is None or case_training.fsrs_card is None:
            return [no_ao, no_ao]

        card = case_training.fsrs_card
        state_klass = card.state.name.lower()
        state_str = f'[{ state_klass }]{ card.state.name }[/{ state_klass }]'
        due = card.due.astimezone()
        now = datetime.now(UTC).astimezone()
        due_str = (
            '[warning]Overdue[/warning]'
            if due <= now
            else f'[no-ao]{ due.strftime("%Y-%m-%d") }[/no-ao]'
        )
        return [state_str, due_str]

    def fsrs_focus_line(self) -> None:
        """Display FSRS session focus and mastery stats if they changed."""
        if not self.fsrs_selection:
            return

        cards = {
            code: ct.fsrs_card
            for code, ct in self.trainings.cases.items()
            if ct.fsrs_card is not None
        }
        focus = FSRSScheduler.compute_session_focus(
            cards, self.fsrs_probabilities,
        )
        mastered, total = FSRSScheduler.compute_mastery(
            cards, self.fsrs_probabilities,
        )
        mastery_str = (
            f'{ mastered }/{ total } mastered' if mastered > 0 else ''
        )
        focus_str = f'{ focus } { mastery_str }'.strip()

        if focus_str == self.fsrs_last_focus:
            return

        self.fsrs_last_focus = focus_str

        self.console.print(
            f'[fsrs]Training Focus:[/fsrs] [context]{ focus_str }[/context]',
        )

    def fsrs_case_line(self, selected_case: Case) -> None:  # noqa: PLR0914
        """Display FSRS card state, metrics, due date and delta."""
        if not self.fsrs_update or self.fsrs_scheduler is None:
            return

        name = selected_case.pretty_name
        case_training = self.trainings.cases.get(selected_case.code)

        if case_training is None or case_training.fsrs_card is None:
            self.console.print(
                f'[fsrs]{ name }[/fsrs] [new]New[/new]',
            )
            return

        card = case_training.fsrs_card
        state_klass = card.state.name.lower()
        inner_scheduler = self.fsrs_scheduler.scheduler

        if card.step is not None:
            total_steps = (
                len(inner_scheduler.relearning_steps)
                if card.state.name == 'Relearning'
                else len(inner_scheduler.learning_steps)
            )
            state_str = (
                f'[{ state_klass }]{ card.state.name }'
                f' ({ card.step + 1 }/{ total_steps })'
                f'[/{ state_klass }]'
            )
        else:
            state_str = (
                f'[{ state_klass }]{ card.state.name }[/{ state_klass }]'
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
            f'[fsrs]{ name }[/fsrs] { state_str }{ due_str }{ metrics_str }',
        )

    @staticmethod
    def format_score_bands(score: float, rating_klass: str) -> str:
        """
        Format the score positioned within a colored band scale.

        Returns a Rich-formatted string like:
            [dim]E<0.5<[/dim][good]G:0.73<1.0[/good][dim]<H<1.5<A[/dim]
        """
        e = f'E<{BAND_EASY}'
        g = f'G<{BAND_GOOD}'
        h = f'H<{BAND_AGAIN}'
        a = 'A'
        bands = [
            (e, 'easy'),
            (g, 'good'),
            (h, 'hard'),
            (a, 'again'),
        ]
        if score < BAND_EASY:
            active = 'easy'
        elif score < BAND_GOOD:
            active = 'good'
        elif score < BAND_AGAIN:
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
        current_state = current_card.state if current_card is not None else None
        if current_state != preview_card.state:
            old_klass = current_state.name.lower() if current_state else 'new'
            old_label = current_state.name if current_state else 'New'
            new_klass = preview_card.state.name.lower()
            new_name = preview_card.state.name
            state_str = (
                f' [{ old_klass }]{ old_label }[/{ old_klass }]'
                f' -> [{ new_klass }]{ new_name }[/{ new_klass }]'
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
        if breakdown is not None:
            bands = self.format_score_bands(breakdown.score, rating_klass)
            suffix = (
                f'\n'
                rf'\[time:{breakdown.time_s:.2f}s'
                f' htm:{breakdown.htm}'
                f' tps:{breakdown.tps:.1f}'
                f' pauses:{breakdown.pauses}'
                f' missed:{breakdown.missed_qtm}'
                f' {bands}]'
            )

        self.console.print(
            f'[fsrs]{ selected_case.pretty_name }[/fsrs] '
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

        breakdown = self.fsrs_rater.rate_with_details(
            solve, self.step, selected_case.code,
        )
        self.fsrs_pending_rating = breakdown

        current_card = (
            self.trainings.cases[selected_case.code].fsrs_card
            if selected_case.code in self.trainings.cases
            else None
        )
        preview_card = self.fsrs_scheduler.update_card(
            current_card,
            breakdown.rating,
        )
        self.fsrs_result_line(
            selected_case,
            breakdown.rating,
            current_card,
            preview_card,
            breakdown,
        )

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

        if self.show_solution and solution:
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

    def save_line(self, *, manual_rating: bool = False) -> None:
        """Display instructions for saving or canceling the solve."""
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

    def solve_line(self, solve: Solve, selected_case: Case) -> None:  # noqa: C901, PLR0912
        """Display training solve results and execution details."""
        self.trainings.add_timing(
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

        extra = ''
        if new_stats.total > 1:
            extra += format_delta(new_stats.delta)

            if new_stats.total >= 3:
                mo3 = new_stats.mo3
                extra += f' [mo3]Mo3 { format_time(mo3) }[/mo3]'

            if new_stats.total >= 5:
                ao5 = new_stats.ao5
                extra += f' [ao5]Ao5 { format_time(ao5) }[/ao5]'

            if new_stats.total >= 12:
                ao12 = new_stats.ao12
                extra += f' [ao12]Ao12 { format_time(ao12) }[/ao12]'

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            extra,
        )

        if new_stats.total > 1:
            mc = 10 + len(str(len(self.stack))) - 1
            if new_stats.best < old_stats.best:
                self.console.print(
                    f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.best) }[/best]',
                    format_delta(new_stats.best - old_stats.best),
                )

            if new_stats.ao5 < old_stats.best_ao5:
                self.console.print(
                    f'[record]:boom:{ "Best Ao5".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao5) }[/best]',
                    format_delta(new_stats.ao5 - old_stats.best_ao5),
                )

            if new_stats.ao12 < old_stats.best_ao12:
                self.console.print(
                    f'[record]:muscle:{ "Best Ao12".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao12) }[/best]',
                    format_delta(new_stats.ao12 - old_stats.best_ao12),
                )

            if new_stats.ao100 < old_stats.best_ao100:
                self.console.print(
                    f'[record]:crown:{ "Best Ao100".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao100) }[/best]',
                    format_delta(new_stats.ao100 - old_stats.best_ao100),
                )

            if new_stats.ao1000 < old_stats.best_ao1000:
                self.console.print(
                    f'[record]:trophy:{ "Best Ao1000".center(mc) }[/record]',
                    f'[best]{ format_time(new_stats.ao1000) }[/best]',
                    format_delta(new_stats.ao1000 - old_stats.best_ao1000),
                )

    async def save_training(
            self,
            selected_case: Case,
            solve: Solve,
    ) -> bool:
        """
        Save the completed training with optional flag modifications.

        Waits for user input to mark the training with a flag (DNF) or
        cancel it. Persists the training to storage and displays confirmation.
        Handles both keyboard and bluetooth gesture input.

        DNF trainings are not saved.

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

        manual = self.fsrs_update and (
            self.bluetooth_interface is None
            or TRAINER_FSRS_RATING == 'manual'
        )
        manual_rating = (
            MANUAL_RATING_KEYS.get(char) if self.fsrs_update else None
        )

        # Any key other than z/k saves; invalid keys in manual mode skip FSRS.
        discard = char in {'z', 'k'}
        skip_fsrs = manual and manual_rating is None

        save_string = ''
        if discard:
            self.trainings.pop_timing(selected_case.code)
            SOUND_PLAYER.save_discarded()
            save_string = 'Training discarded'
        else:
            if (
                not skip_fsrs
                and self.fsrs_update
                and self.fsrs_scheduler is not None
                and self.fsrs_rater is not None
                and selected_case.code in self.trainings.cases
            ):
                case_training = self.trainings.cases[selected_case.code]
                if manual_rating is not None:
                    rating = manual_rating
                else:
                    pending = self.fsrs_pending_rating
                    rating = (
                        pending.rating
                        if pending is not None
                        else self.fsrs_rater.rate(
                                solve, self.step, selected_case.code,
                        )
                    )
                old_card = case_training.fsrs_card
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

    async def start(self) -> bool:  # noqa: C901, PLR0912, PLR0914, PLR0915
        """
        Execute training workflow for single case.

        Returns:
            True to continue training, False to quit.

        """
        self.init_solve()

        fsrs_selected: TrainingCase | None = None
        was_new_case = False
        if self.fsrs_selection and self.fsrs_scheduler is not None:
            cards = {
                code: ct.fsrs_card
                for code, ct in self.trainings.cases.items()
                if ct.fsrs_card is not None
            }
            effective_limit = max(
                0, self.new_cases_limit - self.fsrs_new_cases_introduced,
            )
            chosen_code = self.fsrs_scheduler.select_next_case(
                cards,
                self.fsrs_probabilities,
                new_cases_limit=effective_limit,
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

        self.start_line(cube, selected_case, solution)

        quit_training = await self.scramble_solve()

        if quit_training is not None:
            return quit_training

        quit_training = await self.wait_solve()
        if quit_training:
            return False

        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        flag: SolveFlag = ''
        moves = []
        if self.moves:
            if self.bluetooth_cube and not self.bluetooth_scramble_is_completed:
                flag = DNF

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
            self.counter += 1

            return True

        self.fsrs_pending_rating = None
        self.solve_line(solve, selected_case)

        if not self.free_play:
            if self.fsrs_update:
                self.fsrs_preview_line(solve, selected_case)
            self.save_line(
                manual_rating=(
                    self.fsrs_update and (
                        self.bluetooth_interface is None
                        or TRAINER_FSRS_RATING == 'manual'
                    )
                ),
            )

            session_len_before = len(self.session_data)
            quit_training = await self.save_training(selected_case, solve)

            if was_new_case and len(self.session_data) > session_len_before:
                self.fsrs_new_cases_introduced += 1

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
