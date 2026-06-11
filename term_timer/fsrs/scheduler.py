"""FSRS scheduling logic for case selection."""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from random import choices

from fsrs import Card
from fsrs import Rating
from fsrs import Scheduler
from fsrs import State

# Minimum FSRS stability (days) for a case to be considered mastered.
# Stability represents how long the memory holds at 90% retention.
# 14 days = two-week interval, reliably in long-term memory.
MASTERY_STABILITY_DAYS: float = 14.0

# Cadence policy, not a memory-model parameter: maximum_interval only clamps
# the scheduled due date (min(interval, cap)), never stability/difficulty/the
# rating. Capping at 7 days forces every case back at least weekly. Procedural
# (muscle) memory degrades in fluency (TPS drops, pauses return) long before it
# "lapses" in recall, so a motor pattern is refreshed more often than FSRS
# would space a declarative fact. Because it never touches stability, this knob
# is invisible to the high-stab% trajectory test; its before/after is the
# review cadence, not the rating distribution.
MAXIMUM_INTERVAL_DAYS: int = 7

# Massed/blocked practice in the acquisition phase. learning_steps and
# relearning_steps live in the short-term regime that FSRS itself models only
# crudely, so this is where domain knowledge is injected without fighting the
# DSR model. More short steps make the trainer re-serve a card several times
# within the same session before it graduates to spaced Review: a new case is
# drilled 4 times over ~30 min, a lapsed known case is re-grooved twice before
# re-spacing. This matches the motor-learning rule "massed first to build
# coordination, spaced later to maintain".
#
# steps[0] is the loop period of a failing card: an Again resets the card to
# step 0, due in steps[0]. It must exceed one full rep cycle (scramble +
# execution + review, ~45-90 s) or a failing card re-preempts the session
# before any other case can be served (due cards have absolute priority in
# select_next_case). 2 min lets 1-3 other cases interleave between re-serves
# while keeping all reps within the same session.
LEARNING_STEPS: tuple[timedelta, ...] = (
    timedelta(minutes=2),
    timedelta(minutes=5),
    timedelta(minutes=10),
    timedelta(minutes=15),
)
RELEARNING_STEPS: tuple[timedelta, ...] = (
    timedelta(minutes=2),
    timedelta(minutes=5),
)


class FSRSScheduler:
    """Manages FSRS-based case selection and card updates."""

    def __init__(self) -> None:
        """Initialize the FSRS scheduler."""
        self.scheduler = Scheduler(
            learning_steps=LEARNING_STEPS,
            relearning_steps=RELEARNING_STEPS,
            maximum_interval=MAXIMUM_INTERVAL_DAYS,
            enable_fuzzing=True,
        )

    def update_card(self, card: Card | None, rating: Rating) -> Card:
        """
        Review a card with the given rating and return the updated card.

        Args:
            card: Existing card, or None to create a new one
            rating: FSRS rating from the performance rater

        Returns:
            Updated Card with new scheduling state.

        """
        updated, _ = self.scheduler.review_card(card or Card(), rating)
        return updated

    def select_next_case(
        self,
        cards: dict[str, Card],
        probabilities: dict[str, float],
        new_cases_limit: int,
    ) -> str:
        """
        Select next case to practice using FSRS scheduling.

        Priority order:
        1. Overdue cards (past due date), sorted by urgency
        2. New cards (not yet seen, up to limit), weighted by probability
        3. Weighted-random from all available cases by probability

        Args:
            cards: FSRS cards keyed by case code
            probabilities: All available case codes mapped to their probability
                (how often the case appears in real solves). Used to weight
                random selection so common cases are practised more often.
            new_cases_limit: Maximum number of new cases to introduce

        Returns:
            Case code to practice next.

        """
        due_cards = self.get_due_cards(cards)

        if due_cards:
            return self.prioritize_by_urgency(cards, due_cards)[0]

        new_cards = self.get_new_cards(cards, probabilities, new_cases_limit)

        if new_cards:
            new_weights = [probabilities[c] for c in new_cards]
            return choices(new_cards, weights=new_weights, k=1)[0]  # noqa: S311

        available = list(probabilities.keys())
        if new_cases_limit == 0:
            seen = set(cards.keys())
            available = [c for c in available if c in seen] or available
        weights = [probabilities[c] for c in available]
        return choices(available, weights=weights, k=1)[0]  # noqa: S311

    @staticmethod
    def compute_session_focus(
        cards: dict[str, Card],
        probabilities: dict[str, float],
        new_cases_limit: int,
    ) -> str:
        """
        Determine the training session focus from current card states.

        Mirrors the select_next_case priority order so the label can
        never contradict what the session will actually serve next:

        - ``remediation``/``review`` — one or more cards are due now and
          will be served first (remediation when due lapses are being
          re-grooved)
        - ``exploration`` — nothing due and the session still has budget
          to introduce unseen cases
        - ``learning`` — cards in Learning/Relearning are mid-acquisition
          and will come due again within the session
        - ``maintenance`` — every case is grooved, weighted random
          practice over the seen pool

        Args:
            cards: FSRS cards keyed by case code (only seen cases)
            probabilities: All available case codes with their probabilities
            new_cases_limit: Remaining session budget for unseen cases

        Returns:
            Focus label string, e.g. ``'Learning (8)'`` or
            ``'Review (5 due)'``.

        """
        total = len(probabilities)
        if not cards:
            return f'Exploration (0/{ total } seen)'

        due = FSRSScheduler.get_due_cards(cards)
        if due:
            relearning = [
                c for c in due if cards[c].state == State.Relearning
            ]
            if relearning:
                return f'Remediation ({ len(relearning) } relearning)'
            return f'Review ({ len(due) } due)'

        if FSRSScheduler.get_new_cards(cards, probabilities, new_cases_limit):
            return f'Exploration ({ len(cards) }/{ total } seen)'

        acquiring = [
            c for c, card in cards.items()
            if card.state in {State.Learning, State.Relearning}
        ]
        if acquiring:
            return f'Learning ({ len(acquiring) })'

        return 'Maintenance'

    @staticmethod
    def compute_mastery(
        cards: dict[str, Card],
        probabilities: dict[str, float],
    ) -> tuple[int, int]:
        """
        Count mastered cases out of all available cases.

        A case is mastered when its FSRS card is in Review state and has
        accumulated enough stability to be considered long-term memory.
        The threshold is ``MASTERY_STABILITY_DAYS`` (default 14 days).

        Args:
            cards: FSRS cards keyed by case code (only seen cases)
            probabilities: All available case codes with their probabilities

        Returns:
            ``(mastered, total)`` where ``mastered`` is the number of cases
            meeting the mastery criteria and ``total`` is all available cases.

        """
        total = len(probabilities)
        mastered = sum(
            1
            for card in cards.values()
            if (
                card.state == State.Review
                and (card.stability or 0.0) >= MASTERY_STABILITY_DAYS
            )
        )
        return mastered, total

    @staticmethod
    def get_due_cards(cards: dict[str, Card]) -> list[str]:
        """
        Return case codes for cards that are due or overdue.

        Args:
            cards: FSRS cards keyed by case code

        Returns:
            List of case codes past their scheduled review date.

        """
        now = datetime.now(UTC)
        return [code for code, card in cards.items() if card.due <= now]

    @staticmethod
    def get_new_cards(
        cards: dict[str, Card],
        probabilities: dict[str, float],
        limit: int,
    ) -> list[str]:
        """
        Return all unseen case codes, or empty list when limit is zero.

        Returns the full pool of unseen cases so that the weighted-random
        selection in select_next_case can favour high-probability cases
        naturally, without hard-coding a deterministic top-N order.

        Args:
            cards: FSRS cards keyed by case code (known cases)
            probabilities: All available case codes with their probabilities
            limit: Session budget; when 0 no new cases are returned

        Returns:
            All unseen case codes, or [] when limit is 0.

        """
        if limit == 0:
            return []
        return [c for c in probabilities if c not in cards]

    @staticmethod
    def prioritize_by_urgency(
        cards: dict[str, Card],
        due_cases: list[str],
    ) -> list[str]:
        """
        Sort due cases by urgency (most overdue first).

        Args:
            cards: FSRS cards keyed by case code
            due_cases: Case codes that are due

        Returns:
            Due cases sorted by due date ascending (oldest first).

        """
        return sorted(due_cases, key=lambda code: cards[code].due)
