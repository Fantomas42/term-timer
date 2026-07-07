"""FSRS card state persistence structures."""
from dataclasses import dataclass
from dataclasses import field
from typing import NotRequired
from typing import TypedDict

from fsrs import Card


class FSRSCardData(TypedDict):
    """Serialized FSRS card state stored inside the training JSON."""

    card_id: int
    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: str
    last_review: str | None


class CaseTrainingData(TypedDict):
    """Dictionary representation of training data for a single case."""

    last_date: int
    timings: list[int]
    solution: NotRequired[str]
    fsrs: NotRequired[FSRSCardData]


@dataclass
class CaseTraining:
    """Training data for a single case with timing history."""

    code: str
    last_date: int
    timings: list[int]
    fsrs_card: Card | None = field(default=None)
    solution: str = ''

    def add_timing(self, timing: int, date: int) -> None:
        """
        Add a new timing for this case.

        Args:
            timing: Timing value in milliseconds
            date: Unix timestamp

        """
        self.timings.append(timing)
        self.last_date = date

    @property
    def as_save(self) -> CaseTrainingData:
        """
        Return dictionary representation for serialization.

        Returns:
            Dictionary with last_date, timings, and optional fsrs data.

        """
        data: CaseTrainingData = {
            'last_date': self.last_date,
            'timings': self.timings,
        }
        if self.solution:
            data['solution'] = self.solution

        if self.fsrs_card is not None:
            raw = self.fsrs_card.to_dict()
            data['fsrs'] = FSRSCardData(
                card_id=int(raw['card_id']),
                state=int(raw['state']),
                step=raw['step'],
                stability=raw['stability'],
                difficulty=raw['difficulty'],
                due=str(raw['due']),
                last_review=(
                    str(raw['last_review'])
                    if raw['last_review'] is not None
                    else None
                ),
            )
        return data


@dataclass
class Trainings:
    """Container for all training data for a method/step combination."""

    method: str
    step: str
    cases: dict[str, CaseTraining]

    def add_timing(self, case_code: str, timing: int, date: int) -> int | None:
        """
        Add a timing for a specific case.

        Creates a new CaseTraining entry if the case doesn't exist yet.

        Args:
            case_code: Case identifier (e.g., '27', 'Aa')
            timing: Timing value in milliseconds
            date: Unix timestamp

        Returns:
            The last_date the case had before this timing, or None if
            the entry was just created. Meant to be handed back to
            pop_timing() should the timing be discarded.

        """
        previous = None

        if case_code not in self.cases:
            self.cases[case_code] = CaseTraining(
                code=case_code,
                last_date=date,
                timings=[],
            )
        else:
            previous = self.cases[case_code].last_date

        self.cases[case_code].add_timing(timing, date)

        return previous

    def pop_timing(self, case_code: str, previous_date: int | None) -> None:
        """
        Delete last timing for a specific case.

        Restores the last_date the case had before the popped timing,
        and drops the entry entirely when nothing remains worth keeping
        (no timing, no FSRS card, no custom solution).

        Args:
            case_code: Case identifier (e.g., '27', 'Aa')
            previous_date: last_date to restore, as returned by
                add_timing(); None if the entry was created by it.

        """
        case = self.cases.get(case_code)

        if case is None:
            return

        case.timings.pop()
        empty = (
            not case.timings
            and case.fsrs_card is None
            and not case.solution
        )

        if empty:
            del self.cases[case_code]
        elif previous_date is not None:
            case.last_date = previous_date

    def as_save(self) -> dict[str, CaseTrainingData]:
        """
        Return dictionary representation for serialization.

        Returns:
            Dictionary mapping case codes to their training data.

        """
        return {
            code: case.as_save
            for code, case in self.cases.items()
        }
