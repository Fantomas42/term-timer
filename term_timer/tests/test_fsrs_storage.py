"""Tests for FSRS training storage structures."""
import unittest

from fsrs import Card

from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings


def make_trainings() -> Trainings:
    """
    Build an empty CFOP/PLL Trainings container.

    Returns:
        A Trainings with no cases.

    """
    return Trainings(method='CFOP', step='PLL', cases={})


class TestTrainingsAddTiming(unittest.TestCase):
    """add_timing() returns the last_date to restore on discard."""

    def test_new_case_returns_none(self) -> None:
        """The first timing of a case has no previous date."""
        trainings = make_trainings()
        previous = trainings.add_timing('Aa', 2000, 100)
        self.assertIsNone(previous)
        self.assertEqual(trainings.cases['Aa'].last_date, 100)
        self.assertEqual(trainings.cases['Aa'].timings, [2000])

    def test_known_case_returns_previous_date(self) -> None:
        """A later timing returns the date it overwrote."""
        trainings = make_trainings()
        trainings.add_timing('Aa', 2000, 100)
        previous = trainings.add_timing('Aa', 1800, 200)
        self.assertEqual(previous, 100)
        self.assertEqual(trainings.cases['Aa'].last_date, 200)
        self.assertEqual(trainings.cases['Aa'].timings, [2000, 1800])


class TestTrainingsPopTiming(unittest.TestCase):
    """pop_timing() restores last_date and prunes empty entries."""

    def test_restores_previous_date(self) -> None:
        """Discarding a second attempt restores the previous last_date."""
        trainings = make_trainings()
        trainings.add_timing('Aa', 2000, 100)
        previous = trainings.add_timing('Aa', 1800, 200)

        trainings.pop_timing('Aa', previous)

        self.assertEqual(trainings.cases['Aa'].last_date, 100)
        self.assertEqual(trainings.cases['Aa'].timings, [2000])

    def test_removes_entry_created_by_first_attempt(self) -> None:
        """Discarding the very first attempt removes the empty entry."""
        trainings = make_trainings()
        previous = trainings.add_timing('Aa', 2000, 100)

        trainings.pop_timing('Aa', previous)

        self.assertNotIn('Aa', trainings.cases)
        self.assertNotIn('Aa', trainings.as_save())

    def test_keeps_entry_holding_a_solution(self) -> None:
        """A custom solution is never lost by discarding the only timing."""
        trainings = make_trainings()
        trainings.cases['Aa'] = CaseTraining(
            code='Aa',
            last_date=100,
            timings=[],
            solution="R U R' U'",
        )
        previous = trainings.add_timing('Aa', 2000, 200)

        trainings.pop_timing('Aa', previous)

        self.assertIn('Aa', trainings.cases)
        self.assertEqual(trainings.cases['Aa'].solution, "R U R' U'")
        self.assertEqual(trainings.cases['Aa'].timings, [])
        self.assertEqual(trainings.cases['Aa'].last_date, 100)

    def test_keeps_entry_holding_a_card(self) -> None:
        """An FSRS card is never lost by discarding the only timing."""
        trainings = make_trainings()
        trainings.cases['Aa'] = CaseTraining(
            code='Aa',
            last_date=100,
            timings=[],
            fsrs_card=Card(),
        )
        previous = trainings.add_timing('Aa', 2000, 200)

        trainings.pop_timing('Aa', previous)

        self.assertIn('Aa', trainings.cases)
        self.assertIsNotNone(trainings.cases['Aa'].fsrs_card)
        self.assertEqual(trainings.cases['Aa'].timings, [])
        self.assertEqual(trainings.cases['Aa'].last_date, 100)

    def test_unknown_case_is_a_noop(self) -> None:
        """Popping a timing for an unknown case does nothing."""
        trainings = make_trainings()
        trainings.pop_timing('Aa', None)
        self.assertEqual(trainings.cases, {})
