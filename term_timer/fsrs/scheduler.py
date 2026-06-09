"""FSRS scheduling logic for case selection."""

from datetime import UTC
from datetime import datetime
from random import choices

from fsrs import Card
from fsrs import Rating
from fsrs import Scheduler
from fsrs import State

EXPLORATION_THRESHOLD = 0.2

# Minimum FSRS stability (days) for a case to be considered mastered.
# Stability represents how long the memory holds at 90% retention.
# 14 days = two-week interval, reliably in long-term memory.
MASTERY_STABILITY_DAYS: float = 14.0


class FSRSScheduler:
    """Manages FSRS-based case selection and card updates."""

    def __init__(self) -> None:
        """Initialize the FSRS scheduler."""
        self.scheduler = Scheduler(maximum_interval=30)

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
    ) -> str:
        """
        Determine the training session focus from current card states.

        Returns a short human-readable label with a count, describing what
        kind of work the session is focused on:

        - ``exploration`` — fewer than 20 % of cases have been seen yet
        - ``remediation`` — one or more cards are in Relearning state
          (were in Review but got rated Again)
        - ``learning`` — majority of seen cards are still in Learning state
        - ``review`` — most seen cards are in Review and several are due
        - ``maintenance`` — most cards are in Review with few or no dues

        Args:
            cards: FSRS cards keyed by case code (only seen cases)
            probabilities: All available case codes with their probabilities

        Returns:
            Focus label string, e.g. ``'learning (8)'`` or ``'review (5 due)'``.

        """
        total = len(probabilities)
        if total == 0 or not cards:
            return f'Exploration (0/{total} seen)'

        seen = len(cards)
        if seen / total < EXPLORATION_THRESHOLD:
            return f'Exploration ({seen}/{total} seen)'

        relearning = [c for c, card in cards.items()
                      if card.state == State.Relearning]
        if relearning:
            return f'Remediation ({len(relearning)} relearning)'

        now = datetime.now(UTC)
        learning = [c for c, card in cards.items()
                    if card.state == State.Learning]
        review = [c for c, card in cards.items()
                  if card.state == State.Review]
        due = [c for c, card in cards.items() if card.due <= now]

        if len(learning) >= len(review):
            return f'Learning ({len(learning)})'

        if due:
            return f'Review ({len(due)} due)'

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
