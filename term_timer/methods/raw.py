from typing import ClassVar

from term_timer.methods.base import Analyser


class RawAnalyser(Analyser):
    name = 'Raw'
    step_list = ('RAW',)
    norms: ClassVar[dict[str, dict[str, float]]] = {
        'solve': {
            'recognition': 0,
            'execution': 100,
        },
    }

    def compute_progress(self, *args, **kwargs):  # noqa: ARG002
        return 0, []
