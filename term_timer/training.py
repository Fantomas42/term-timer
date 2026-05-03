"""Training data."""
from dataclasses import dataclass
from typing import TypedDict


class CaseTrainingData(TypedDict):
    """Dictionary representation of training data for a single case."""

    last_date: int
    timings: list[int]


@dataclass
class CaseTraining:
    """Training data for a single case with timing history."""

    code: str
    last_date: int
    timings: list[int]

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
            Dictionary with last_date and timings for JSON serialization.

        """
        return {
            'last_date': self.last_date,
            'timings': self.timings,
        }


@dataclass
class Trainings:
    """Container for all training data for a method/step combination."""

    method: str
    step: str
    cases: dict[str, CaseTraining]

    def add_timing(self, case_code: str, timing: int, date: int) -> None:
        """
        Add a timing for a specific case.

        Creates a new CaseTraining entry if the case doesn't exist yet.

        Args:
            case_code: Case identifier (e.g., '27', 'Aa')
            timing: Timing value in milliseconds
            date: Unix timestamp

        """
        if case_code not in self.cases:
            self.cases[case_code] = CaseTraining(
                code=case_code,
                last_date=date,
                timings=[],
            )
        self.cases[case_code].add_timing(timing, date)

    def pop_timing(self, case_code: str) -> None:
        """
        Delete last timing for a specific case.

        Args:
            case_code: Case identifier (e.g., '27', 'Aa')

        """
        if case_code in self.cases:
            self.cases[case_code].timings.pop()

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
