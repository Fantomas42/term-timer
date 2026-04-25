"""Layer-by-layer method analysis."""
from typing import ClassVar

from cubing_algs.annotations import CubeFacelets

from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import Analyser


class LBLAnalyser(Analyser):
    """
    Analyser for Layer-by-Layer solving method.

    Tracks solve progress through Cross, F1L, F2L, and Last Layer steps.
    """

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
            'recognition': (0, 30),
            'execution': (70, 100),
        },
    }

    def compute_progress(
            self,
            facelets: CubeFacelets,
            progress: int,
    ) -> tuple[int, list[str]]:
        """
        Calculate solve progress through LBL steps.

        Returns:
            Tuple of (current step index, list of case identifiers).

        """
        current_progress = progress

        for name in self.step_list[progress:-1]:
            if self.check_step(name, facelets):
                current_progress += 1
            else:
                break

        return current_progress, []

    def correct_summary(self, summary: list[StepSummary]) -> None:
        """
        Apply LBL-specific corrections to step summary.

        Inserts skipped steps if necessary.
        """
        all_steps = [s['name'] for s in summary]

        for step_position, step_name in enumerate(self.step_list):
            if step_name not in all_steps:
                summary.insert(
                    step_position,
                    self.create_skipped_summary(step_name),
            )
