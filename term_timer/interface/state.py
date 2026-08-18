"""State management and logging for solve tracking."""
import asyncio
import logging
import time

from term_timer.publisher import PUBLISHER
from term_timer.publisher import STATE_TOPIC

logger = logging.getLogger(__name__)


class State:
    """Mixin providing state management and logging."""

    def __init__(self) -> None:
        """Initialize state tracking."""
        super().__init__()

        self.state = ''
        self.state_event = asyncio.Event()

    def set_state(self, state: str, timestamp: int | None = None) -> None:
        """Set the current state and log the transition."""
        previous, self.state = self.state, state
        at = timestamp or time.perf_counter_ns()

        logger.info(
            'Passing to state %s: %s',
            state.upper().ljust(10),
            at,
        )

        # The nine states of a solve are the skeleton of a session, and
        # the transition is the only place naming them all: a subscriber
        # follows the whole cycle without knowing a single command.
        PUBLISHER.publish(
            STATE_TOPIC,
            {
                'state': state,
                'previous': previous,
                'at': at,
            },
        )

        self.state_event.set()
