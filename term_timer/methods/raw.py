"""Raw method analysis with no step detection."""

from typing import ClassVar

from cubing_algs.constants import INITIAL_STATE

from term_timer.methods.base import Analyser
from term_timer.methods.types import StepInfo


class RawAnalyser(Analyser):
    name = 'Raw'
    step_list = ('RAW',)
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {
        'solve': {
            'recognition': 0,
            'execution': 100,
        },
    }

    def split_steps(self) -> dict[str, StepInfo]:
        steps: dict[str, StepInfo] = {}

        steps[self.step_list[0]] = {
            'moves': list(range(len(self.solution))),
            'increment': 1,
            'case_infos': [],
            'facelets': INITIAL_STATE,
        }

        return steps
