import logging

logger = logging.getLogger(__name__)


class State:
    state = 'init'

    def set_state(self, state, extra=''):
        self.state = state
        logger.info(
            'Passing to state %s %s',
            state.upper(), extra,
        )
