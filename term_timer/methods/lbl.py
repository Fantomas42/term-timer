"""Layer-by-layer method analysis."""

from typing import ClassVar

from cubing_algs.algorithm import Algorithm

from term_timer.methods.base import Analyser
from term_timer.methods.types import StepSummary


class LBLAnalyser(Analyser):
    name = 'LBL'
    step_list = ('Cross', 'F1L', 'F2L', 'LL')
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {
        'moves': {
            'Cross': 6,
            'F2L': 30,
        },
        'percent': {
            'Cross': 12.0,
            'F2L': 50.0,
            'LL': 38,
        },
        'solve': {
            'recognition': (20, 30),
            'execution': (70, 80),
        },
    }

    def compute_progress(self, facelets: str,
                         progress: int) -> tuple[int, list[str]]:
        current_progress = progress

        for name in self.step_list[progress:-1]:
            if self.check_step(name, facelets, self.orientation_faces):
                current_progress += 1
            else:
                break

        return current_progress, []

    @staticmethod
    def correct_summary(summary: list[StepSummary]) -> None:
        # Skipped F1L insert
        if summary[1]['name'] != 'F1L':
            summary.insert(
                1,
                {
                    'type': 'skipped',
                    'name': 'F1L',
                    'moves': Algorithm(),
                    'moves_reoriented': Algorithm(),
                    'moves_humanized': Algorithm(),
                    'moves_prettified': Algorithm(),
                    'times': [],
                    'index': [],
                    'qtm': 0,
                    'total': 0,
                    'execution': 0,
                    'recognition': 0,
                    'post_pause': 0,
                    'aufs': [None, None],
                    'total_percent': 0,
                    'execution_percent': 0,
                    'recognition_percent': 0,
                    'step_execution_percent': 0,
                    'step_recognition_percent': 0,
                    'increment': 0,
                    'case': 'SKIP',
                    'case_infos': [],
                    'facelets': '',
                },
            )
