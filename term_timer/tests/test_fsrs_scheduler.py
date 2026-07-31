"""Tests for the FSRS FSRSScheduler."""
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from fsrs import Card
from fsrs import Rating
from fsrs import State

from term_timer.fsrs.scheduler import MASTERY_STABILITY_DAYS
from term_timer.fsrs.scheduler import FSRSScheduler


def make_card(
    due_offset_days: float = 1.0,
    state: State = State.Learning,
    stability: float | None = None,
    last_review_offset_days: float | None = None,
    difficulty: float | None = None,
) -> Card:
    """
    Create a Card with controlled due date, state, and stability.

    Args:
        due_offset_days: Days from now (negative = overdue).
        state: FSRS card state.
        stability: FSRS stability value in days.
        last_review_offset_days: Days from now for the last review
            (negative = past). None leaves the card unreviewed.
        difficulty: FSRS difficulty value; py-fsrs requires it to review
            a card in Review state.

    Returns:
        A Card with the requested attributes.

    """
    card = Card()
    card.due = datetime.now(UTC) + timedelta(days=due_offset_days)
    card.state = state
    if stability is not None:
        card.stability = stability
    if difficulty is not None:
        card.difficulty = difficulty
    if last_review_offset_days is not None:
        card.last_review = datetime.now(UTC) + timedelta(
            days=last_review_offset_days,
        )
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


class TestMissedThisSession(unittest.TestCase):
    """missed_this_session() detects cards reviewed since session start."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()

    def test_never_reviewed_card_is_not_a_miss(self) -> None:
        """A card without last_review belongs to the backlog."""
        card = make_card(due_offset_days=-1.0)
        self.assertFalse(self.scheduler.missed_this_session(card))

    def test_card_reviewed_before_session_is_not_a_miss(self) -> None:
        """A card last reviewed yesterday belongs to the backlog."""
        card = make_card(
            due_offset_days=-1.0,
            last_review_offset_days=-1.0,
        )
        self.assertFalse(self.scheduler.missed_this_session(card))

    def test_card_reviewed_in_session_is_a_miss(self) -> None:
        """A card reviewed after the session started is a miss."""
        card = make_card(due_offset_days=-0.001)
        card.last_review = self.scheduler.session_start + timedelta(
            minutes=2,
        )
        self.assertTrue(self.scheduler.missed_this_session(card))

    def test_card_reviewed_at_session_start_is_a_miss(self) -> None:
        """The session start instant itself counts as in-session."""
        card = make_card(due_offset_days=-0.001)
        card.last_review = self.scheduler.session_start
        self.assertTrue(self.scheduler.missed_this_session(card))


class TestPrioritizeDue(unittest.TestCase):
    """prioritize_due() re-serves in-session misses before the backlog."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()

    def missed_card(self, due_offset_minutes: float = -1.0) -> Card:
        """
        Build a card missed during the current session.

        Args:
            due_offset_minutes: Minutes from now for the due date.

        Returns:
            A due card whose last review is inside the session.

        """
        card = make_card(due_offset_days=0.0)
        card.due = datetime.now(UTC) + timedelta(minutes=due_offset_minutes)
        card.last_review = self.scheduler.session_start + timedelta(
            seconds=30,
        )
        return card

    def test_in_session_miss_comes_before_older_backlog(self) -> None:
        """A miss due 1 min ago beats a backlog card due 30 days ago."""
        cards = {
            'A': make_card(due_offset_days=-30.0),
            'B': self.missed_card(),
        }
        result = self.scheduler.prioritize_due(cards, ['A', 'B'])
        self.assertEqual(result, ['B', 'A'])

    def test_backlog_keeps_urgency_order(self) -> None:
        """Backlog cards stay sorted oldest-due first behind the miss."""
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=-3.0),
            'C': self.missed_card(),
        }
        result = self.scheduler.prioritize_due(cards, ['A', 'B', 'C'])
        self.assertEqual(result, ['C', 'B', 'A'])

    def test_several_misses_sorted_by_due(self) -> None:
        """Multiple in-session misses are ordered oldest-due first."""
        cards = {
            'A': self.missed_card(due_offset_minutes=-1.0),
            'B': self.missed_card(due_offset_minutes=-5.0),
        }
        result = self.scheduler.prioritize_due(cards, ['A', 'B'])
        self.assertEqual(result, ['B', 'A'])

    def test_without_miss_matches_plain_urgency(self) -> None:
        """With no in-session miss the queue is the urgency order."""
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=-3.0),
            'C': make_card(due_offset_days=-0.5),
        }
        codes = ['A', 'B', 'C']
        self.assertEqual(
            self.scheduler.prioritize_due(cards, codes),
            FSRSScheduler.prioritize_by_urgency(cards, codes),
        )

    def test_empty_due_returns_empty(self) -> None:
        """No due case returns an empty queue."""
        self.assertEqual(self.scheduler.prioritize_due({}, []), [])


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


class TestSelectNextCaseSessionReserve(unittest.TestCase):
    """A case missed in-session is re-served without clearing the backlog."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()
        self.probs = {'A': 0.4, 'B': 0.3, 'C': 0.3}
        self.cards = {
            'A': make_card(
                due_offset_days=-30.0,
                state=State.Review,
                stability=60.0,
                difficulty=5.0,
            ),
            'B': make_card(
                due_offset_days=-29.0,
                state=State.Review,
                stability=60.0,
                difficulty=5.0,
            ),
            'C': make_card(
                due_offset_days=-28.0,
                state=State.Review,
                stability=60.0,
                difficulty=5.0,
            ),
        }

    def test_missed_case_waits_for_its_learning_step(self) -> None:
        """The miss is not due yet, so the backlog keeps flowing."""
        self.assertEqual(
            self.scheduler.select_next_case(self.cards, self.probs, 0),
            'A',
        )
        self.cards['A'] = self.scheduler.update_card(
            self.cards['A'], Rating.Again,
        )
        self.assertEqual(
            self.scheduler.select_next_case(self.cards, self.probs, 0),
            'B',
        )

    def test_missed_case_preempts_backlog_once_step_elapsed(self) -> None:
        """Once the step elapsed the miss beats a 28-day-old backlog card."""
        self.cards['A'] = self.scheduler.update_card(
            self.cards['A'], Rating.Again,
        )
        # The 2 min learning step has now passed.
        self.cards['A'].due = datetime.now(UTC) - timedelta(seconds=1)

        self.assertEqual(
            self.scheduler.select_next_case(self.cards, self.probs, 0),
            'A',
        )

    def test_passed_case_does_not_preempt(self) -> None:
        """A case rated Good in-session is rescheduled, never re-served."""
        self.cards['A'] = self.scheduler.update_card(
            self.cards['A'], Rating.Good,
        )
        self.assertNotIn('A', FSRSScheduler.get_due_cards(self.cards))
        self.assertEqual(
            self.scheduler.select_next_case(self.cards, self.probs, 0),
            'B',
        )

    def test_backlog_order_untouched_without_miss(self) -> None:
        """With nothing missed the queue is the plain urgency order."""
        served: list[str] = []
        for _ in range(3):
            code = self.scheduler.select_next_case(self.cards, self.probs, 0)
            served.append(code)
            self.cards[code] = self.scheduler.update_card(
                self.cards[code], Rating.Good,
            )
        self.assertEqual(served, ['A', 'B', 'C'])


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

    def test_reviewed_due_case_can_repeat(self) -> None:
        """
        Due cards are exempt: massed repetition is intentional.

        Each rep is rated Again and its learning step is then elapsed by
        hand: the exemption covers the massed practice the steps exist
        for, not a card left untouched (see
        TestSelectNextCaseUnratedDeferral).
        """
        cards = {
            'A': make_card(due_offset_days=-1.0),
            'B': make_card(due_offset_days=1.0),
            'C': make_card(due_offset_days=1.0),
        }
        for _ in range(3):
            result = self.scheduler.select_next_case(cards, self.probs, 5)
            self.assertEqual(result, 'A')
            cards['A'] = self.scheduler.update_card(cards['A'], Rating.Again)
            cards['A'].due = datetime.now(UTC) - timedelta(seconds=1)

    def test_anti_repeat_pool_all_zero_weights(self) -> None:
        """Excluding the last case from an all-zero pool still draws."""
        probs = {'A': 0.0, 'B': 0.0}
        cards = {c: make_card(due_offset_days=1.0) for c in probs}
        self.scheduler.last_case = 'A'
        result = self.scheduler.select_next_case(cards, probs, 5)
        self.assertEqual(result, 'B')


class TestSelectNextCaseUnratedDeferral(unittest.TestCase):
    """A due case served but left unrated is deferred within the session."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()
        self.probs = {'A': 0.5, 'B': 0.3, 'C': 0.2}

    @staticmethod
    def review_card(due_offset_days: float) -> Card:
        """
        Build a Review card with a history, as a session loads it.

        A Review card has necessarily been reviewed: its stability, its
        difficulty and its last review are part of the state, and the
        7-day interval below is what MAXIMUM_INTERVAL_DAYS produces.

        Returns:
            A Review card last reviewed a week before it fell due.

        """
        return make_card(
            due_offset_days=due_offset_days,
            state=State.Review,
            stability=10.0,
            difficulty=5.0,
            last_review_offset_days=due_offset_days - 7.0,
        )

    def test_unrated_due_case_is_not_served_again(self) -> None:
        """Nothing is rated, so the most overdue case must not loop."""
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
        }
        first = self.scheduler.select_next_case(cards, self.probs, 0)
        second = self.scheduler.select_next_case(cards, self.probs, 0)

        self.assertEqual(first, 'A')
        self.assertEqual(second, 'B')

    def test_unrated_session_walks_the_whole_backlog(self) -> None:
        """Three unrated reps serve three distinct cases."""
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
            'C': self.review_card(-1.0),
        }
        served = [
            self.scheduler.select_next_case(cards, self.probs, 0)
            for _ in range(3)
        ]

        self.assertEqual(served, ['A', 'B', 'C'])

    def test_deferred_backlog_falls_through_to_new_cases(self) -> None:
        """With the whole backlog deferred, an unseen case is introduced."""
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
        }
        probs = {'A': 0.5, 'B': 0.3, 'D': 0.2}
        for _ in range(2):
            self.scheduler.select_next_case(cards, probs, 5)

        self.assertEqual(
            self.scheduler.select_next_case(cards, probs, 5),
            'D',
        )

    def test_deferred_backlog_falls_through_to_fallback(self) -> None:
        """No new case left: the weighted fallback keeps the session going."""
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
            'C': self.review_card(1.0),
        }
        # Only C carries weight, so the fallback draw is deterministic.
        probs = {'A': 0.0, 'B': 0.0, 'C': 1.0}
        for _ in range(2):
            self.scheduler.select_next_case(cards, probs, 0)

        self.assertEqual(
            self.scheduler.select_next_case(cards, probs, 0),
            'C',
        )

    def test_unrated_new_cases_are_offered_once_each(self) -> None:
        """
        An unseen case served unrated does not come back either.

        Without a rating no card is created, so the case stays unseen
        and the new-case budget is never consumed: the new bucket would
        otherwise feed the session for ever, never reaching the pool.
        """
        cards = {
            'C': self.review_card(1.0),
            'D': self.review_card(1.0),
        }
        # A and B carry no weight, so the fallback can only draw C or D.
        probs = {'A': 0.0, 'B': 0.0, 'C': 0.5, 'D': 0.5}
        served = [
            self.scheduler.select_next_case(cards, probs, 5)
            for _ in range(6)
        ]

        self.assertEqual(sorted(served[:2]), ['A', 'B'])
        self.assertEqual(set(served[2:]), {'C', 'D'})

    def test_rated_new_case_is_freed_by_its_own_card(self) -> None:
        """
        An unseen case is snapshotted as None; rating it frees it.

        The snapshot of a case served without a card is None, and a
        rating is what gives it one: the card carries a real last
        review, which is what must lift the deferral.
        """
        cards: dict[str, Card] = {}
        # B carries no weight, so the unseen draw is deterministic.
        probs = {'A': 1.0, 'B': 0.0}
        self.assertEqual(self.scheduler.select_next_case(cards, probs, 5), 'A')

        cards['A'] = self.scheduler.update_card(None, Rating.Good)

        # Rated, so out of the deferral, but scheduled minutes away.
        self.assertNotIn('A', FSRSScheduler.get_due_cards(cards))

        # The learning step has now passed.
        cards['A'].due = datetime.now(UTC) - timedelta(seconds=1)

        self.assertEqual(self.scheduler.select_next_case(cards, probs, 5), 'A')

    def test_single_case_pool_is_served_as_last_resort(self) -> None:
        """One case in the pool: the deferral must not starve the session."""
        probs = {'A': 1.0}
        cards = {'A': self.review_card(-10.0)}

        for _ in range(3):
            self.assertEqual(
                self.scheduler.select_next_case(cards, probs, 0),
                'A',
            )

    def test_rated_case_comes_back_once_its_step_elapsed(self) -> None:
        """
        A rep finally rated Again is re-served like any missed card.

        Rating is what takes a case out of the deferral, but it also
        reschedules it: the card only comes back once its learning step
        has elapsed, never on the very next draw.
        """
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
        }
        self.scheduler.select_next_case(cards, self.probs, 0)
        self.scheduler.select_next_case(cards, self.probs, 0)
        cards['A'] = self.scheduler.update_card(cards['A'], Rating.Again)

        # Rated, so out of the deferral, but scheduled 2 min away.
        self.assertNotIn('A', FSRSScheduler.get_due_cards(cards))

        # The 2 min learning step has now passed.
        cards['A'].due = datetime.now(UTC) - timedelta(seconds=1)

        self.assertEqual(
            self.scheduler.select_next_case(cards, self.probs, 0),
            'A',
        )

    def test_deferral_does_not_outlive_the_session(self) -> None:
        """The next session finds the card due, since it was never rated."""
        cards = {
            'A': self.review_card(-10.0),
            'B': self.review_card(-3.0),
        }
        self.scheduler.select_next_case(cards, self.probs, 0)

        self.assertEqual(
            FSRSScheduler().select_next_case(cards, self.probs, 0),
            'A',
        )


class TestSelectNextCaseAcquisition(unittest.TestCase):
    """The random fallback leaves cards in acquisition to their steps."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()
        self.probs = {'A': 0.5, 'B': 0.5}

    def test_learning_card_not_due_is_never_served_by_fallback(self) -> None:
        """A Learning card scheduled minutes away is not maintenance."""
        cards = {
            'A': make_card(due_offset_days=1.0, state=State.Review),
            'B': make_card(due_offset_days=0.003, state=State.Learning),
        }
        for _ in range(50):
            result = self.scheduler.select_next_case(cards, self.probs, 0)
            self.assertEqual(result, 'A')

    def test_relearning_card_not_due_is_never_served_by_fallback(self) -> None:
        """A lapsed card keeps the breathing room of its relearning step."""
        cards = {
            'A': make_card(due_offset_days=1.0, state=State.Review),
            'B': make_card(due_offset_days=0.001, state=State.Relearning),
        }
        for _ in range(50):
            result = self.scheduler.select_next_case(cards, self.probs, 0)
            self.assertEqual(result, 'A')

    def test_acquisition_card_is_served_once_due(self) -> None:
        """The filter only defers the card, the due path still serves it."""
        cards = {
            'A': make_card(due_offset_days=1.0, state=State.Review),
            'B': make_card(due_offset_days=-0.001, state=State.Learning),
        }
        result = self.scheduler.select_next_case(cards, self.probs, 0)
        self.assertEqual(result, 'B')

    def test_pool_of_acquisition_cards_only_still_draws(self) -> None:
        """A pool left with nothing but acquisition cards keeps serving."""
        cards = {
            'A': make_card(due_offset_days=0.003, state=State.Learning),
            'B': make_card(due_offset_days=0.003, state=State.Relearning),
        }
        for _ in range(20):
            result = self.scheduler.select_next_case(cards, self.probs, 0)
            self.assertIn(result, self.probs)

    def test_filter_never_unlocks_the_new_case_budget(self) -> None:
        """An exhausted budget outranks the filter: no unseen case leaks."""
        probs = {'A': 0.4, 'B': 0.3, 'C': 0.3}
        cards = {'A': make_card(due_offset_days=0.003, state=State.Learning)}
        for _ in range(20):
            result = self.scheduler.select_next_case(cards, probs, 0)
            self.assertEqual(result, 'A')


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
    """compute_session_focus() describes the case being served."""

    def setUp(self) -> None:  # noqa: D102
        self.scheduler = FSRSScheduler()

    def test_exploration_when_no_cards_seen(self) -> None:
        """No cards seen yet → exploration."""
        probs = dict.fromkeys('ABCD', 0.25)
        focus, detail = self.scheduler.compute_session_focus({}, probs, 5)
        self.assertEqual(focus, 'Exploration')
        self.assertEqual(detail, '5 new left · 0/4 seen')

    def test_exploration_when_unseen_case_selected(self) -> None:
        """The selected case has no card yet → exploration."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {'A': make_card(state=State.Learning)}
        self.scheduler.last_case = 'B'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 4)
        self.assertEqual(focus, 'Exploration')
        self.assertEqual(detail, '4 new left · 1/4 seen')

    def test_exploration_detail_drops_exhausted_budget(self) -> None:
        """No new-case budget left → the counter is not displayed."""
        probs = dict.fromkeys('ABCD', 0.25)
        focus, detail = self.scheduler.compute_session_focus({}, probs, 0)
        self.assertEqual(focus, 'Exploration')
        self.assertEqual(detail, '0/4 seen')

    def test_review_when_due_case_selected(self) -> None:
        """A due Review case is served → review with the backlog size."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            'A': make_card(state=State.Review, due_offset_days=-1.0),
            'B': make_card(state=State.Review, due_offset_days=-1.0),
            'C': make_card(state=State.Review, due_offset_days=1.0),
            'D': make_card(state=State.Review, due_offset_days=1.0),
        }
        self.scheduler.last_case = 'A'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Review')
        self.assertEqual(detail, '2 due')

    def test_backlog_wins_over_a_minority_of_relearning(self) -> None:
        """A relearning minority does not take over the review label."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            c: make_card(state=State.Review, due_offset_days=-1.0)
            for c in 'ABCD'
        }
        cards['D'] = make_card(state=State.Relearning, due_offset_days=-0.1)
        self.scheduler.last_case = 'A'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Review')
        self.assertEqual(detail, '4 due (1 relearning)')

    def test_relearning_when_relearning_case_selected(self) -> None:
        """The served card leads the label, whatever the backlog is."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            c: make_card(state=State.Review, due_offset_days=-1.0)
            for c in 'ABCD'
        }
        cards['D'] = make_card(state=State.Relearning, due_offset_days=-0.1)
        self.scheduler.last_case = 'D'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Relearning')
        self.assertEqual(detail, '4 due')

    def test_learning_when_learning_case_selected(self) -> None:
        """A due card mid-acquisition keeps its own state label."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {'A': make_card(state=State.Learning, due_offset_days=-0.1)}
        self.scheduler.last_case = 'A'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 0)
        self.assertEqual(focus, 'Learning')
        self.assertEqual(detail, '1 due')

    def test_maintenance_when_selected_case_not_due(self) -> None:
        """Nothing due, the pool is served at random → maintenance."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            c: make_card(state=State.Review, due_offset_days=5.0)
            for c in 'ABCD'
        }
        self.scheduler.last_case = 'C'
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Maintenance')
        self.assertEqual(detail, '4/4 seen')

    def test_focus_follows_the_selection(self) -> None:
        """select_next_case drives the label, without recomputing it."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            'A': make_card(state=State.Review, due_offset_days=-1.0),
            'B': make_card(state=State.Relearning, due_offset_days=-0.1),
        }
        selected = self.scheduler.select_next_case(cards, probs, 5)
        self.assertEqual(selected, 'A')
        focus, _ = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Review')

    def test_without_selection_the_due_head_is_described(self) -> None:
        """No case selected yet → the head of the due queue is described."""
        probs = dict.fromkeys('ABCD', 0.25)
        cards = {
            'A': make_card(state=State.Review, due_offset_days=-1.0),
            'B': make_card(state=State.Relearning, due_offset_days=-2.0),
        }
        focus, detail = self.scheduler.compute_session_focus(cards, probs, 5)
        self.assertEqual(focus, 'Relearning')
        self.assertEqual(detail, '2 due')


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
