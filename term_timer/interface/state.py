"""State management and logging for solve tracking."""
import logging
import time

logger = logging.getLogger(__name__)


class State:
    """Mixin providing state management and logging."""

    def __init__(self) -> None:
        """Initialize state tracking."""
        super().__init__()

        self.state = ''

    def set_state(self, state: str, timestamp: int | None = None) -> None:
        """Set the current state and log the transition."""
        self.state = state

        logger.info(
            'Passing to state %s: %s',
            state.upper().ljust(10),
            timestamp or time.perf_counter_ns(),
        )
