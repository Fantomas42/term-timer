"""FSRS scheduling logic for case selection."""

from datetime import UTC
from datetime import datetime
from random import choice

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
        available_cases: list[str],
        new_card_limit: int,
    ) -> str:
        """
        Select next case to practice using FSRS scheduling.

        Priority order:
        1. Overdue cards (past due date)
        2. New cards (not yet seen, up to limit)
        3. Random from available cases

        Args:
            cards: FSRS cards keyed by case code
            available_cases: All available case codes
            new_card_limit: Maximum number of new cards to introduce

        Returns:
            Case code to practice next.

        """
        due_cards = self.get_due_cards(cards)

        if due_cards:
            return self.prioritize_by_urgency(cards, due_cards)[0]

        new_cards = self.get_new_cards(cards, available_cases, new_card_limit)

        if new_cards:
            return choice(new_cards)  # noqa: S311

        return choice(available_cases)  # noqa: S311

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
        available_cases: list[str],
        limit: int,
    ) -> list[str]:
        """
        Return unseen case codes up to limit.

        Args:
            cards: FSRS cards keyed by case code (known cases)
            available_cases: All available case codes
            limit: Maximum number of new cases to return

        Returns:
            List of unseen case codes (up to limit).

        """
        new_cases = [c for c in available_cases if c not in cards]
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
