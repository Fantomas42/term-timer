"""Tests for the FSRS FSRSScheduler."""
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fsrs import Card
from fsrs import State

from term_timer.fsrs.scheduler import MASTERY_STABILITY_DAYS
from term_timer.fsrs.scheduler import FSRSScheduler


def make_card(
    due_offset_days: float = 1.0,
    state: State = State.Learning,
    stability: float | None = None,
) -> Card:
    """
    Create a Card with controlled due date, state, and stability.

    Args:
        due_offset_days: Days from now (negative = overdue).
        state: FSRS card state.
        stability: FSRS stability value in days.

    Returns:
        A Card with the requested attributes.

    """
    card = Card()
    card.due = datetime.now(UTC) + timedelta(days=due_offset_days)
    card.state = state
    if stability is not None:
        card.stability = stability
    return card


class TestGetDueCards(unittest.TestCase):
    """get_due_cards() returns only cards whose due date is in the past."""

    def test_overdue_card_is_returned(self) -> None:
        """Card due yesterday is returned."""
        cards = {'A': make_card(due_offset_days=-1.0)}
        result = FSRSScheduler.get_due_cards(cards)
        self.assertEqual(result, ['A'])

    def test_future_card_is_not_returned(self) -> None:
        """Card due tomorrow is not returned."""
        cards = {'A': make_card(due_offset_days=1.0)}
        result = FSRSScheduler.get_due_cards(cards)
        self.assertEqual(result, [])

    def test_empty_cards_returns_empty(self) -> None:
        """Empty card dict returns empty list."""
        self.assertEqual(FSRSScheduler.get_due_cards({}), [])

    def test_mixed_due_and_future(self) -> None:
        """Only the overdue card is returned from a mixed set."""
        cards = {
            'A': make_card(due_offset_days=-2.0),
            'B': make_card(due_offset_days=1.0),
        }
        result = FSRSScheduler.get_due_cards(cards)
        self.assertEqual(result, ['A'])


class TestGetNewCards(unittest.TestCase):
    """get_new_cards() returns all unseen cases, or [] when limit is 0."""

    def setUp(self) -> None:  # noqa: D102
        self.cards = {'A': make_card()}
        self.probs = {'A': 0.5, 'B': 0.3, 'C': 0.2}

    def test_seen_cases_excluded(self) -> None:
        """Case A is already seen and should not appear in new cards."""
        result = FSRSScheduler.get_new_cards(self.cards, self.probs, limit=5)
        self.assertNotIn('A', result)

    def test_returns_all_unseen_when_limit_positive(self) -> None:
        """All unseen cases are returned when limit > 0."""
        result = FSRSScheduler.get_new_cards({}, self.probs, limit=2)
        self.assertEqual(set(result), {'A', 'B', 'C'})

    def test_limit_zero_returns_empty(self) -> None:
        """limit=0 returns no new cases."""
        result = FSRSScheduler.get_new_cards({}, self.probs, limit=0)
        self.assertEqual(result, [])

    def test_all_seen_returns_empty(self) -> None:
        """All cases already seen returns empty list."""
        cards = {c: make_card() for c in self.probs}
        result = FSRSScheduler.get_new_cards(cards, self.probs, limit=5)
        self.assertEqual(result, [])


class TestPrioritizeByUrgency(unittest.TestCase):
    """prioritize_by_urgency() sorts due cards oldest-due first."""

    def test_most_overdue_first(self) -> None:
        """Most overdue card comes first."""
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=-3.0),
            'C': make_card(due_offset_days=-0.5),
        }
        result = FSRSScheduler.prioritize_by_urgency(cards, ['A', 'B', 'C'])
        self.assertEqual(result[0], 'B')

    def test_order_ascending_by_due(self) -> None:
        """Cards are sorted by due date ascending (oldest first)."""
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=-2.0),
        }
        result = FSRSScheduler.prioritize_by_urgency(cards, ['A', 'B'])
        self.assertEqual(result, ['B', 'A'])


class TestSelectNextCase(unittest.TestCase):
    """select_next_case() follows the overdue > new > random priority."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()
        self.probs = {'A': 0.5, 'B': 0.3, 'C': 0.2}

    def test_overdue_takes_priority_over_new(self) -> None:
        """An overdue card is always selected over introducing a new case."""
        cards = {'A': make_card(due_offset_days=-1.0)}
        # B and C are unseen (new), but A is overdue
        result = self.scheduler.select_next_case(cards, self.probs, 5)
        self.assertEqual(result, 'A')

    def test_new_card_introduced_when_no_due(self) -> None:
        """A new case is introduced when no card is overdue and limit allows."""
        # A has a future review, B and C are unseen
        cards = {'A': make_card(due_offset_days=1.0)}
        for _ in range(20):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertIn(result, {'B', 'C'})

    def test_new_card_limit_zero_prevents_new_cases(self) -> None:
        """new_card_limit=0 never introduces unseen cases."""
        cards = {'A': make_card(due_offset_days=1.0)}
        for _ in range(30):
            result = self.scheduler.select_next_case(cards, self.probs, 0)
            self.assertEqual(result, 'A')

    def test_new_card_limit_zero_fallback_when_all_unseen(self) -> None:
        """When limit=0 but no card has been seen, new cases are allowed."""
        for _ in range(10):
            result = self.scheduler.select_next_case({}, self.probs, 0)
            self.assertIn(result, self.probs)

    def test_random_fallback_when_no_due_no_new(self) -> None:
        """Falls back to weighted random when all cases seen and none due."""
        cards = {c: make_card(due_offset_days=1.0) for c in self.probs}
        for _ in range(20):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertIn(result, self.probs)

    def test_result_always_in_probabilities(self) -> None:
        """Selected case is always a valid key from probabilities."""
        cards = {'A': make_card(due_offset_days=-1.0)}
        for _ in range(20):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertIn(result, self.probs)


class TestSelectNextCaseAntiRepeat(unittest.TestCase):
    """The random fallback never serves the same case twice in a row."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()
        self.probs = {'A': 0.5, 'B': 0.3, 'C': 0.2}

    def test_fallback_never_repeats_previous_case(self) -> None:
        """Two consecutive fallback draws never return the same case."""
        cards = {c: make_card(due_offset_days=1.0) for c in self.probs}
        previous = None
        for _ in range(50):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertNotEqual(result, previous)
            previous = result

    def test_fallback_excludes_case_served_by_due_path(self) -> None:
        """A case just served as due is excluded from the next fallback."""
        self.scheduler.last_case = 'A'
        cards = {c: make_card(due_offset_days=1.0) for c in self.probs}
        for _ in range(30):
            self.scheduler.last_case = 'A'
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertIn(result, {'B', 'C'})

    def test_single_case_pool_can_repeat(self) -> None:
        """A pool of one case keeps serving it."""
        probs = {'A': 1.0}
        cards = {'A': make_card(due_offset_days=1.0)}
        for _ in range(5):
            result = self.scheduler.select_next_case(cards, probs, 5)
            self.assertEqual(result, 'A')

    def test_due_case_can_repeat(self) -> None:
        """Due cards are exempt: massed repetition is intentional."""
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=1.0),
            'C': make_card(due_offset_days=1.0),
        }
        for _ in range(3):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertEqual(result, 'A')

    def test_anti_repeat_pool_all_zero_weights(self) -> None:
        """Excluding the last case from an all-zero pool still draws."""
        probs = {'A': 0.0, 'B': 0.0}
        cards = {c: make_card(due_offset_days=1.0) for c in probs}
        self.scheduler.last_case = 'A'
        result = self.scheduler.select_next_case(cards, probs, 5)
        self.assertEqual(result, 'B')


class TestWeightedChoice(unittest.TestCase):
    """weighted_choice() guards random.choices against all-zero weights."""

    def test_all_zero_pool_falls_back_to_uniform(self) -> None:
        """An all-zero pool draws uniformly instead of raising."""
        probs = {'A': 0.0, 'B': 0.0, 'C': 0.0}
        for _ in range(20):
            result = FSRSScheduler.weighted_choice(list(probs), probs)
            self.assertIn(result, probs)

    def test_zero_weight_case_stays_unselectable_in_mixed_pool(self) -> None:
        """A zero-weight case keeps its real weight in a mixed pool."""
        probs = {'A': 1.0, 'B': 0.0}
        for _ in range(30):
            result = FSRSScheduler.weighted_choice(list(probs), probs)
            self.assertEqual(result, 'A')

    def test_normal_pool_returns_a_candidate(self) -> None:
        """A normal pool returns one of its candidates."""
        probs = {'A': 0.5, 'B': 0.3, 'C': 0.2}
        for _ in range(20):
            result = FSRSScheduler.weighted_choice(list(probs), probs)
            self.assertIn(result, probs)

    def test_select_next_case_all_zero_probabilities(self) -> None:
        """select_next_case survives an all-zero probability pool."""
        scheduler = FSRSScheduler()
        probs = {'A': 0.0, 'B': 0.0, 'C': 0.0}
        # New-card path: A seen with a future due, B/C unseen.
        cards = {'A': make_card(due_offset_days=1.0)}
        for _ in range(10):
            result = scheduler.select_next_case(cards, probs, 5)
            self.assertIn(result, {'B', 'C'})
        # Random fallback path: everything seen, nothing due.
        cards = {c: make_card(due_offset_days=1.0) for c in probs}
        for _ in range(10):
            result = scheduler.select_next_case(cards, probs, 5)
            self.assertIn(result, probs)


class TestComputeSessionFocus(unittest.TestCase):
    """compute_session_focus() mirrors the select_next_case priority."""

    def test_exploration_when_no_cards_seen(self) -> None:
        """No cards seen yet → exploration."""
        probs = dict.fromkeys('ABCD', 0.25)
        focus = FSRSScheduler.compute_session_focus({}, probs, 5)
        self.assertIn('Exploration', focus)

    def test_exploration_while_budget_remains(self) -> None:
        """Nothing due, unseen cases and budget left → exploration."""
        probs = {str(i): 0.1 for i in range(10)}
        cards = {'0': make_card(state=State.Learning)}
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertIn('Exploration', focus)

    def test_exploration_ends_when_budget_exhausted(self) -> None:
        """Unseen cases remain but no budget → not exploration."""
        probs = {str(i): 0.1 for i in range(10)}
        cards = {'0': make_card(state=State.Learning)}
        focus = FSRSScheduler.compute_session_focus(cards, probs, 0)
        self.assertNotIn('Exploration', focus)

    def test_due_takes_priority_over_exploration(self) -> None:
        """A due card wins over remaining new-case budget."""
        probs = {str(i): 0.1 for i in range(10)}
        cards = {'0': make_card(state=State.Review, due_offset_days=-1.0)}
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertIn('Review', focus)

    def test_remediation_when_relearning_due(self) -> None:
        """A due card in Relearning state → remediation."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {c: make_card(state=State.Review) for c in 'ABCD'}
        cards['A'] = make_card(state=State.Relearning, due_offset_days=-0.1)
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertIn('Remediation', focus)

    def test_learning_when_acquisition_in_flight(self) -> None:
        """Cards in Learning, none due, nothing unseen → learning."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {c: make_card(state=State.Learning) for c in 'ABCD'}
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertIn('Learning', focus)

    def test_review_when_cards_due(self) -> None:
        """Some cards due → review with due count."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            'A': make_card(state=State.Review, due_offset_days=-1.0),
            'B': make_card(state=State.Review, due_offset_days=-1.0),
            'C': make_card(state=State.Review, due_offset_days=1.0),
            'D': make_card(state=State.Review, due_offset_days=1.0),
        }
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Review (2 due)')

    def test_maintenance_when_review_nothing_due(self) -> None:
        """All cases seen, in Review and none due → maintenance."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {c: make_card(state=State.Review, due_offset_days=5.0)
                 for c in 'ABCD'}
        focus = FSRSScheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Maintenance')


class TestComputeMastery(unittest.TestCase):
    """compute_mastery() counts Review cards above the stability threshold."""

    def setUp(self) -> None:  # noqa: D102
        self.probs = dict.fromkeys('ABCD', 0.25)

    def test_review_above_threshold_counts(self) -> None:
        """Review card with stability >= MASTERY_STABILITY_DAYS is mastered."""
        cards = {'A': make_card(
            state=State.Review,
            stability=MASTERY_STABILITY_DAYS,
        )}
        mastered, total = FSRSScheduler.compute_mastery(cards, self.probs)
        self.assertEqual(mastered, 1)
        self.assertEqual(total, 4)

    def test_review_below_threshold_not_mastered(self) -> None:
        """Review card below stability threshold is not mastered."""
        cards = {'A': make_card(
            state=State.Review,
            stability=MASTERY_STABILITY_DAYS - 1,
        )}
        mastered, _ = FSRSScheduler.compute_mastery(cards, self.probs)
        self.assertEqual(mastered, 0)

    def test_learning_card_not_mastered(self) -> None:
        """Learning card is not mastered regardless of stability."""
        cards = {'A': make_card(
            state=State.Learning,
            stability=MASTERY_STABILITY_DAYS + 10,
        )}
        mastered, _ = FSRSScheduler.compute_mastery(cards, self.probs)
        self.assertEqual(mastered, 0)

    def test_no_cards_returns_zero(self) -> None:
        """Empty card dict returns (0, total)."""
        mastered, total = FSRSScheduler.compute_mastery({}, self.probs)
        self.assertEqual(mastered, 0)
        self.assertEqual(total, 4)

    def test_total_reflects_probabilities_not_cards(self) -> None:
        """Total is the number of cases in probabilities, not seen cards."""
        cards = {'A': make_card(state=State.Review, stability=20.0)}
        _, total = FSRSScheduler.compute_mastery(cards, self.probs)
        self.assertEqual(total, len(self.probs))
