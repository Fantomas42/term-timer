import logging
import time

logger = logging.getLogger(__name__)


class State:
    state = ''

    def set_state(self, state, timestamp=None):
        self.state = state
        logger.info(
            'Passing to state %s: %s',
            state.upper().ljust(10),
            timestamp or time.perf_counter_ns(),
        )
