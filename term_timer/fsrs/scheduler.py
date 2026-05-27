"""FSRS scheduling logic for case selection."""

from datetime import UTC
from datetime import datetime
from random import choices

from term_timer.fsrs.types import Card
from term_timer.fsrs.types import Rating
from term_timer.fsrs.types import Scheduler


class FSRSScheduler:
    """Manages FSRS-based case selection and card updates."""

    def __init__(self) -> None:
        """Initialize the FSRS scheduler."""
        self.scheduler = Scheduler()

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
        new_card_limit: int,
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
            new_card_limit: Maximum number of new cards to introduce

        Returns:
            Case code to practice next.

        """
        due_cards = self.get_due_cards(cards)

        if due_cards:
            return self.prioritize_by_urgency(cards, due_cards)[0]

        new_cards = self.get_new_cards(cards, probabilities, new_card_limit)

        if new_cards:
            new_weights = [probabilities[c] for c in new_cards]
            return choices(new_cards, weights=new_weights, k=1)[0]  # noqa: S311

        available = list(probabilities.keys())
        weights = list(probabilities.values())
        return choices(available, weights=weights, k=1)[0]  # noqa: S311

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
        Return unseen case codes up to limit, ordered by probability.

        Higher-probability cases (more common in real solves) are introduced
        first so the learner practises the most impactful cases sooner.

        Args:
            cards: FSRS cards keyed by case code (known cases)
            probabilities: All available case codes with their probabilities
            limit: Maximum number of new cases to return

        Returns:
            List of unseen case codes (up to limit), highest probability first.

        """
        new_cases = [c for c in probabilities if c not in cards]
        new_cases.sort(key=lambda c: probabilities[c], reverse=True)
        return new_cases[:limit]

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
