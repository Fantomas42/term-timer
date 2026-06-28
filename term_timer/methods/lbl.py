"""Layer-by-layer method analysis."""
from typing import ClassVar

from cubing_algs.annotations import CubeFacelets

from term_timer.methods.annotations import MethodNorms
from term_timer.methods.annotations import StepSummary
from term_timer.methods.base import Analyser


class LBLAnalyser(Analyser):
    """
    Analyser for Layer-by-Layer solving method.

    Tracks solve progress through First Layer (FL), Second Layer (SL),
    and Last Layer (LL) steps.
    """

    name = 'LBL'
    step_list = ('FL', 'SL', 'LL')
    norms: ClassVar[MethodNorms] = {
        'moves': {
            'FL': 24,
            'SL': 30,
            'LL': 45,
        },
        'percent': {
            'FL': 25.0,
            'SL': 25.0,
            'LL': 50.0,
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
