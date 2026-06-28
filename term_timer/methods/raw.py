"""Raw method analysis with no step detection."""
from typing import ClassVar

from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3

from term_timer.methods.annotations import MethodNorms
from term_timer.methods.annotations import NormRange
from term_timer.methods.annotations import StepInfo
from term_timer.methods.base import Analyser


class RawAnalyser(Analyser):
    """
    Analyser for raw solves with no step detection.

    Treats entire solve as a single step without method-specific analysis.
    """

    name = 'Raw'
    step_list = ('RAW',)
    norms: ClassVar[MethodNorms] = {
        'moves': {},
        'percent': {
            'RAW': 100.0,
        },
        'recognition': {
            'RAW': NormRange(0.0, 0.0),
        },
        'execution': {
            'RAW': NormRange(100.0, 100.0),
        },
        'solve': {
            'recognition': NormRange(0.0, 0.0),
            'execution': NormRange(100.0, 100.0),
        },
    }

    def split_steps(self) -> dict[str, StepInfo]:
        """
        Split solution into steps (single RAW step).

        Returns:
            Dictionary with single RAW step containing all moves.

        """
        steps: dict[str, StepInfo] = {}

        steps[self.step_list[0]] = {
            'moves': list(range(len(self.solution))),
            'increment': 1,
            'case_infos': [],
            'facelets': SOLVED_FACELETS_3x3x3,
        }

        return steps
