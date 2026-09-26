"""Tests for FSRS training storage structures."""
import json
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fsrs import Card
from fsrs import State

from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.in_out import fsrs_card_from_data


def make_trainings() -> Trainings:
    """
    Build an empty CFOP/PLL Trainings container.

    Returns:
        A Trainings with no cases.

    """
    return Trainings(method='CFOP', step='PLL', cases={})


def round_trip(card: Card) -> Card:
    """
    Serialize a card through JSON and deserialize it back.

    Returns:
        The card rebuilt by fsrs_card_from_data.

    Raises:
        AssertionError: If no card comes back from the round-trip.

    """
    training = CaseTraining(
        code='Aa',
        last_date=100,
        timings=[2000],
        fsrs_card=card,
    )
    data = json.loads(json.dumps(training.as_save))
    restored = fsrs_card_from_data(data)
    if restored is None:
        msg = 'No FSRS card came back from the round-trip'
        raise AssertionError(msg)
    return restored


class TestFSRSCardRoundTrip(unittest.TestCase):
    """FSRS cards survive an as_save -> JSON -> load round-trip intact."""

    def test_learning_card(self) -> None:
        """A Learning card round-trips with its step preserved."""
        card = Card()
        restored = round_trip(card)
        self.assertEqual(restored.to_dict(), card.to_dict())

    def test_review_card_keeps_step_none(self) -> None:
        """A Review card keeps step None, per the py-fsrs invariant."""
        now = datetime.now(tz=UTC)
        card = Card(
            state=State.Review,
            stability=15.0,
            difficulty=5.0,
            due=now,
            last_review=now,
        )
        restored = round_trip(card)
        self.assertIsNone(restored.step)
        self.assertEqual(restored.to_dict(), card.to_dict())

    def test_relearning_card(self) -> None:
        """A Relearning card round-trips with its step preserved."""
        now = datetime.now(tz=UTC)
        card = Card(
            state=State.Relearning,
            step=0,
            stability=3.0,
            difficulty=6.0,
            due=now,
            last_review=now,
        )
        restored = round_trip(card)
        self.assertEqual(restored.step, 0)
        self.assertEqual(restored.to_dict(), card.to_dict())

    def test_legacy_review_card_with_step_zero_is_repaired(self) -> None:
        """A legacy file with a Review card at step 0 loads step None."""
        now = datetime.now(tz=UTC).isoformat()
        data = {
            'last_date': 100,
            'timings': [2000],
            'fsrs': {
                'card_id': 1751800000000,
                'state': int(State.Review),
                'step': 0,
                'stability': 15.0,
                'difficulty': 5.0,
                'due': now,
                'last_review': now,
            },
        }
        card = fsrs_card_from_data(data)  # type: ignore[arg-type]
        if card is None:
            self.fail('No FSRS card parsed from legacy data')
        self.assertEqual(card.state, State.Review)
        self.assertIsNone(card.step)


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


class TestCaseTrainingBest(unittest.TestCase):
    """best is the fastest timing of a case, DNFs aside."""

    def test_best(self) -> None:
        """The smallest positive timing wins."""
        case = CaseTraining(code='Aa', last_date=0, timings=[0, 1500, 1200])

        self.assertEqual(case.best, 1200)

    def test_no_timing(self) -> None:
        """A case without timing has no best."""
        case = CaseTraining(code='Aa', last_date=0, timings=[])

        self.assertEqual(case.best, 0)


class TestSummarizeStates(unittest.TestCase):
    """summarize_states recaps the cases of a step by card state."""

    def setUp(self) -> None:
        """Build cases spread over the card states."""
        self.now = datetime.now(UTC)

        def card(state: State, due_days: float) -> Card:
            built = Card(state=state, step=None if state == State.Review else 0)
            built.due = self.now + timedelta(days=due_days)
            return built

        self.trainings = Trainings(method='CFOP', step='PLL', cases={
            'Aa': CaseTraining(
                code='Aa', last_date=0, timings=[1500, 1200],
                fsrs_card=card(State.Review, -1),
            ),
            'Ab': CaseTraining(
                code='Ab', last_date=0, timings=[2000],
                fsrs_card=card(State.Review, 5),
            ),
            'E': CaseTraining(
                code='E', last_date=0, timings=[3000],
                fsrs_card=card(State.Learning, -0.1),
            ),
            'F': CaseTraining(code='F', last_date=0, timings=[2500]),
            'Ga': CaseTraining(
                code='Ga', last_date=0, timings=[1000],
                fsrs_card=card(State.Review, -3),
            ),
        })

    def test_counts_by_state(self) -> None:
        """Each asked case lands in its state, unseen ones in New."""
        summary = self.trainings.summarize_states(
            ['Aa', 'Ab', 'E', 'F', 'H'], self.now,
        )

        self.assertEqual(list(summary), [
            'New', 'Learning', 'Relearning', 'Review', 'Stable',
        ])
        self.assertEqual(
            {label: row.count for label, row in summary.items()},
            {
                'New': 2, 'Learning': 1, 'Relearning': 0,
                'Review': 1, 'Stable': 1,
            },
        )

    def test_overdue_and_bests(self) -> None:
        """Overdues count past due cards, bests only practiced cases."""
        summary = self.trainings.summarize_states(
            ['Aa', 'Ab', 'E', 'F', 'H'], self.now,
        )

        self.assertEqual(summary['Review'].overdue, 1)
        self.assertEqual(summary['Learning'].overdue, 1)
        self.assertEqual(summary['Stable'].overdue, 0)
        self.assertEqual(summary['Review'].bests, [1200])
        self.assertEqual(summary['New'].bests, [2500])

    def test_only_asked_cases(self) -> None:
        """Cases of the file outside the asked codes are ignored."""
        summary = self.trainings.summarize_states(['Aa'], self.now)

        self.assertEqual(sum(row.count for row in summary.values()), 1)
