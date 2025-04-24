from cubing_algs.algorithm import Algorithm

from term_timer.methods.base import Analyser


class LBLAnalyser(Analyser):
    name = 'LBL'
    step_list = ('Cross', 'F1L', 'F2L', 'LL')
    norms = {
        'moves': {
            'Cross': 6,
            'F2L': 30,
        },
        'percent': {
            'Cross': 12.0,
            'F2L': 50.0,
            'LL': 38,
        },
    }

    def compute_progress(self, cube):
        progress = 0
        facelets = cube.as_twophase_facelets

        for name in self.step_list[:-1]:
            if self.check_step(name, facelets):
                progress += 1
            else:
                break

        return progress, []

    def correct_summary(self, summary):
        # Skipped F1L insert
        if summary[1]['name'] != 'F1L':
            summary.insert(
                1,
                {
                    'type': 'skipped',
                    'name': 'F1L',
                    'moves': [],
                    'times': [],
                    'total': 0,
                    'execution': 0,
                    'inspection': 0,
                    'total_percent': 0,
                    'execution_percent': 0,
                    'inspection_percent': 0,
                    'reconstruction': Algorithm(),
                    'increment': 0,
                    'cases': ['SKIP'],
                    'facelets': '',
                },
            )
