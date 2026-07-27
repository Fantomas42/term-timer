"""FSRS scheduling logic for case selection."""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from random import choices

from fsrs import Card
from fsrs import Rating
from fsrs import Scheduler
from fsrs import State

from term_timer.constants import STABILITY_LONG_TERM_DAYS
from term_timer.formatter import fsrs_state_label

# Minimum FSRS stability (days) for a case to be considered mastered.
# Stability represents how long the memory holds at 90% retention.
# 14 days = two-week interval, reliably in long-term memory.
# Shared with the rating floor — see term_timer/constants.py.
MASTERY_STABILITY_DAYS: float = STABILITY_LONG_TERM_DAYS

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
        self.last_case: str | None = None
        self.session_start = datetime.now(UTC)

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
        1. Overdue cards (past due date), missed in-session first, then
           by urgency
        2. New cards (not yet seen, up to limit), weighted by probability
        3. Weighted-random by probability over the cases ready for
           maintenance — cards still walking their learning steps are
           left to their schedule (see ``in_acquisition``), unless the
           pool holds nothing else

        The random fallback never serves the same case twice in a row
        (when the pool allows it). Due cards are exempt: immediate
        repetition of a due card is the massed practice the learning
        steps are designed for. New cards cannot repeat by construction
        (a served case gains a card and leaves the new pool).

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
            self.last_case = self.prioritize_due(cards, due_cards)[0]
            return self.last_case

        new_cards = self.get_new_cards(cards, probabilities, new_cases_limit)

        if new_cards:
            self.last_case = self.weighted_choice(new_cards, probabilities)
            return self.last_case

        available = list(probabilities.keys())
        if new_cases_limit == 0:
            seen = set(cards.keys())
            available = [c for c in available if c in seen] or available

        ready = [c for c in available if not self.in_acquisition(cards.get(c))]
        available = ready or available

        if len(available) > 1 and self.last_case in available:
            available = [c for c in available if c != self.last_case]

        self.last_case = self.weighted_choice(available, probabilities)
        return self.last_case

    @staticmethod
    def in_acquisition(card: Card | None) -> bool:
        """
        Tell whether a card is still walking its learning steps.

        Called from the random fallback, which is only reached when
        nothing is due: a Learning or Relearning card seen there is
        necessarily scheduled minutes away, waiting for its next step.
        Serving it early short-circuits the massed practice
        LEARNING_STEPS exist for — measured on a real F2L session, a
        card rated Good and scheduled 5 minutes out was drawn back
        under a minute later and graduated to Review on that rep.

        Args:
            card: FSRS card of a case, or None when the case is unseen

        Returns:
            True when the card is in Learning or Relearning.

        """
        return card is not None and card.state in {
            State.Learning, State.Relearning,
        }

    @staticmethod
    def weighted_choice(
        candidates: list[str],
        probabilities: dict[str, float],
    ) -> str:
        """
        Pick a case code at random, weighted by its probability.

        Probabilities default to 0 in cubing_algs, and random.choices
        raises ValueError when every weight is zero: an all-zero pool
        falls back to a uniform draw. A zero-weight case in a mixed
        pool keeps its real weight and stays unselectable.

        Returns:
            One case code from the candidates.

        """
        weights = [probabilities[c] for c in candidates]

        if not any(weights):
            weights = [1.0] * len(candidates)

        return choices(candidates, weights=weights, k=1)[0]  # noqa: S311

    def focus_case(self, cards: dict[str, Card]) -> str | None:
        """
        Tell which case the focus line describes.

        The focus line is displayed after ``select_next_case`` has run,
        so the case is already picked: reading ``last_case`` back is what
        makes the label structurally unable to contradict what is served,
        without replaying the priority order a second time. The fallback
        only serves callers that describe a session before selecting
        anything (report scripts).

        Args:
            cards: FSRS cards keyed by case code

        Returns:
            Case code the session is about to serve, or None when nothing
            is selected and nothing is due.

        """
        if self.last_case is not None:
            return self.last_case

        due = self.get_due_cards(cards)
        if due:
            return self.prioritize_due(cards, due)[0]

        return None

    def compute_session_focus(
        self,
        cards: dict[str, Card],
        probabilities: dict[str, float],
        new_cases_limit: int,
    ) -> tuple[str, str]:
        """
        Describe the training session focus from the case being served.

        The label is read from the served case itself rather than from a
        scan of the pool, so it says what the session does next instead
        of what it could have done:

        - the state label of a due case (``Review``, ``Relearning``,
          ``Learning``) — the same wording ``fsrs_case_line`` prints just
          below, for the same card
        - ``Exploration`` — an unseen case is introduced
        - ``Maintenance`` — nothing due, weighted random over the pool

        The detail carries the counters the label cannot: the size of the
        due backlog is the actionable number of a training session, and a
        label taken from a single card would otherwise hide it.

        Args:
            cards: FSRS cards keyed by case code (only seen cases)
            probabilities: All available case codes with their probabilities
            new_cases_limit: Remaining session budget for unseen cases

        Returns:
            Tuple of the focus label and its detail, e.g.
            ``('Review', '50 due (5 relearning)')``.

        """
        total = len(probabilities)
        seen = len(cards)
        selected = self.focus_case(cards)

        if selected is not None and selected in cards:
            card = cards[selected]

            if card.due <= datetime.now(UTC):
                return (
                    fsrs_state_label(card)[0],
                    self.due_detail(cards, card),
                )

            return 'Maintenance', f'{ seen }/{ total } seen'

        detail = f'{ seen }/{ total } seen'
        if new_cases_limit > 0:
            detail = f'{ new_cases_limit } new left · { detail }'

        return 'Exploration', detail

    @staticmethod
    def due_detail(cards: dict[str, Card], served: Card) -> str:
        """
        Count the due backlog, and the relearning cases it contains.

        The relearning count is dropped when the served card is itself
        relearning: it is then the headline of the label, and repeating
        it as a secondary counter says nothing more.

        Args:
            cards: FSRS cards keyed by case code
            served: Card the session is about to serve

        Returns:
            Detail string, e.g. ``'50 due (5 relearning)'``.

        """
        due = FSRSScheduler.get_due_cards(cards)
        detail = f'{ len(due) } due'

        if served.state == State.Relearning:
            return detail

        relearning = sum(
            1 for code in due if cards[code].state == State.Relearning
        )
        if relearning:
            detail = f'{ detail } ({ relearning } relearning)'

        return detail

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

    def missed_this_session(self, card: Card) -> bool:
        """
        Tell whether a card was already reviewed during this session.

        A card reviewed in-session and *not* missed is rescheduled days
        away, so it cannot be due: among due cards this predicate isolates
        exactly the ones missed a few minutes ago, whose learning step has
        now elapsed.

        Args:
            card: FSRS card to test

        Returns:
            True when the card's last review happened in this session.

        """
        return (
            card.last_review is not None
            and card.last_review >= self.session_start
        )

    def prioritize_due(
            self,
            cards: dict[str, Card],
            due_cases: list[str],
        ) -> list[str]:
        """
        Sort due cases, re-serving the misses of the current session first.

        Absolute due date alone cannot express "come back in 2 minutes":
        a card missed in-session is due minutes ago against a backlog due
        weeks ago, so urgency sorting buries it at the end of the queue and
        the learning steps never fire (measured: 25 intervening cases on a
        50-case OLL backlog). Re-serving it first is the massed practice
        LEARNING_STEPS exist for; the rest of the queue keeps the plain
        urgency order, so the backlog is still cleared oldest-first.

        Args:
            cards: FSRS cards keyed by case code
            due_cases: Case codes that are due

        Returns:
            In-session misses (oldest due first), then the remaining due
            cases by urgency.

        """
        missed: list[str] = []
        backlog: list[str] = []

        for code in due_cases:
            if self.missed_this_session(cards[code]):
                missed.append(code)
            else:
                backlog.append(code)

        return (
            self.prioritize_by_urgency(cards, missed)
            + self.prioritize_by_urgency(cards, backlog)
        )

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
