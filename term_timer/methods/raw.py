from typing import ClassVar

from term_timer.methods.base import Analyser


class RawAnalyser(Analyser):
    name = 'Raw'
    step_list = ('RAW',)
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {
        'solve': {
            'recognition': 0,
            'execution': 100,
        },
    }

    def compute_progress(self, _facelets: str) -> tuple[int, list[str]]:
        return 0, []
