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
        """
        Set the current state and log the transition.

        Args:
            state: The state being entered.
            timestamp: Instant of the transition, on the monotonic
                clock the stopwatch times solves on, defaulting to the
                instant this is called. Given by the callers that time
                the transition themselves, so that the state changes at
                the instant the solve says it does, not at the one the
                display got round to it.

        """
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
        #
        # "at" is a monotonic counter in nanoseconds, from the clock the
        # stopwatch times solves on. It has no origin a subscriber can
        # relate to anything: only the difference between two of them
        # means something, and the envelope carries the wall clock.
        PUBLISHER.publish(
            STATE_TOPIC,
            {
                'state': state,
                'previous': previous,
                'at': at,
            },
        )

        self.state_event.set()
