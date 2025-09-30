from typing import ClassVar
from typing import Never

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

    def compute_progress(self, *_args, **_kwargs) -> tuple[int, list[Never]]:
        return 0, []
