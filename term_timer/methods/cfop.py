from cubing_algs.algorithm import Algorithm

from term_timer.methods.base import Analyser


class CFOPAnalyser(Analyser):
    name = 'CFOP'
    step_list = ('Cross', 'F2L', 'OLL', 'PLL')
    norms = {
        'moves': {
            'Cross': 6,
            'F2L': 30,
            'OLL': 10,
            'PLL': 15,
        },
        'percent': {
            'Cross': 12.0,
            'F2L': 50.0,
            'OLL': 16.5,
            'PLL': 21.5,
        },
    }

    def compute_progress(self, cube):
        progress = 0
        facelets = cube.as_twophase_facelets

        for name in self.step_list:
            if self.check_step(name, facelets):
                progress += 1
            else:
                break

        return progress, []


class CF4OPAnalyser(Analyser):
    name = 'CF4OP'
    step_list = ('Cross', 'F2L 1', 'F2L 2', 'F2L 3', 'F2L 4', 'OLL', 'PLL')
    norms = {
        'moves': {
            'Cross': 6,
            'XCross': 8,
            'XXCross': 10,
            'XXXCross': 12,
            'XXXXCross': 14,
            'F2L': 30,
            'OLL': 10,
            'PLL': 15,
        },
        'percent': {
            'Cross': 12.0,
            'XCross': 16.0,
            'F2L': 50.0,
            'F2L 1': 12.5,
            'F2L 2': 12.5,
            'F2L 3': 12.5,
            'F2L 4': 12.5,
            'OLL': 16.5,
            'PLL': 21.5,
        },
    }

    def compute_progress(self, cube):
        facelets = cube.as_twophase_facelets

        if not self.check_step('Cross', facelets):
            return 0, []

        if not self.check_step('OLL', facelets):
            name = ['F2L 1', 'F2L 2', 'F2L 3', 'F2L 4']
            pair = ['FL', 'FR', 'BL', 'BR']

            score = 1
            pairs = []

            for n, p in zip(name, pair, strict=True):
                result = self.check_step(n, facelets)
                if result:
                    score += 1
                    pairs.append(p)

            return score, pairs

        return 6, []

    def correct_summary(self, summary):
        if summary[0]['name'] == 'F2L 1':
            summary[0]['name'] = 'XCross'

        elif summary[0]['name'] == 'F2L 2':
            summary[0]['name'] = 'XXCross'

        elif summary[0]['name'] == 'F2L 3':
            summary[0]['name'] = 'XXXCross'

        elif summary[0]['name'] == 'F2L 4':
            summary[0]['name'] = 'XXXXCross'

        for i, info in enumerate(summary):
            if info['increment'] > 1:
                if 'F2L ' in info['name']:
                    previous = summary[i - 1]
                    name = previous['name']
                    if 'F2L ' in name:
                        previous['name'] += f'+{ int(name[-1]) + 1 }'
                    else:
                        info['name'] = 'F2L 1+2'

                if 'OLL' in info['name']:
                    info['name'] = 'F2L 4'

        f2l = {
            'type': 'virtual',
            'name': 'F2L',
            'moves': [],
            'times': [],
            'total': 0,
            'execution': 0,
            'inspection': 0,
            'total_percent': 0,
            'execution_percent': 0,
            'inspection_percent': 0,
            'reconstruction': Algorithm(),
        }

        insert_f2l = False
        for info in summary:
            if 'F2L ' in info['name']:
                info['type'] = 'substep'

                insert_f2l = True
                f2l['moves'].extend(info['moves'])
                f2l['times'].extend(info['times'])
                f2l['total'] += info['total']
                f2l['execution'] += info['execution']
                f2l['inspection'] += info['inspection']
                f2l['total_percent'] += info['total_percent']
                f2l['execution_percent'] += info['execution_percent']
                f2l['inspection_percent'] += info['inspection_percent']
                f2l['reconstruction'].extend(info['reconstruction'])

        if insert_f2l:
            summary.insert(1, f2l)
