"""Tests for in out."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.in_out import load_solves
from term_timer.in_out import load_trainings
from term_timer.in_out import save_trainings


class TestInOut(unittest.TestCase):
    """Tests for solve loading and saving functionality."""

    @patch('term_timer.in_out.SOLVES_DIRECTORY', Path('/mock/path'))
    @patch('pathlib.Path.exists')
    def test_load_solves_non_existing_file(self, mock_exists: Mock) -> None:
        """Test loading solves from a non-existing file returns empty list."""
        mock_exists.return_value = False

        solves = load_solves(3, 'default')

        self.assertEqual(solves, [])


class TestTrainingsSolution(unittest.TestCase):
    """Tests for the custom per-case solution persistence."""

    def test_as_save_includes_solution_when_set(self) -> None:
        """A non-empty solution is serialized under the solution key."""
        case = CaseTraining(
            code='Sune',
            last_date=1700000000,
            timings=[1234],
            solution="R U R' U R U2 R'",
        )

        self.assertEqual(case.as_save['solution'], "R U R' U R U2 R'")

    def test_as_save_omits_empty_solution(self) -> None:
        """An empty solution leaves the solution key out of the payload."""
        case = CaseTraining(
            code='Sune',
            last_date=1700000000,
            timings=[1234],
        )

        self.assertNotIn('solution', case.as_save)

    def test_load_trainings_reads_solution(self) -> None:
        """load_trainings deserializes the solution key into the case."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'CFOP').mkdir()
            (directory / 'CFOP' / 'OLL.json').write_text(
                json.dumps(
                    {
                        'Sune': {
                            'last_date': 1700000000,
                            'timings': [1234],
                            'solution': "R U R' U R U2 R'",
                        },
                    },
                ),
                encoding='utf-8',
            )

            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                trainings = load_trainings('CFOP', 'OLL')

            self.assertEqual(
                trainings.cases['Sune'].solution,
                "R U R' U R U2 R'",
            )

    def test_solution_survives_save_round_trip(self) -> None:
        """A manually-added solution is preserved across save/load."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            trainings = Trainings(
                method='CFOP',
                step='OLL',
                cases={
                    'Sune': CaseTraining(
                        code='Sune',
                        last_date=1700000000,
                        timings=[1234],
                        solution="R U R' U R U2 R'",
                    ),
                },
            )

            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                save_trainings(trainings)
                reloaded = load_trainings('CFOP', 'OLL')

            self.assertEqual(
                reloaded.cases['Sune'].solution,
                "R U R' U R U2 R'",
            )
