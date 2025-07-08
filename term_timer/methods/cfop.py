import json
from functools import cached_property
from pathlib import Path
from typing import ClassVar

from cubing_algs.algorithm import Algorithm

from term_timer.constants import SECOND
from term_timer.methods.base import Analyser

DATA_DIRECTORY = Path(__file__).parent
OLL_PATH = DATA_DIRECTORY / 'oll.json'
PLL_PATH = DATA_DIRECTORY / 'pll.json'

OLL_MASKS = {}
PLL_MASKS = {}
OLL_INFO = {}
PLL_INFO = {}
OLL_SETUPS = {}
PLL_SETUPS = {}


def load_and_fill(path, masks, info, setups):
    with path.open('r') as fd:
        for kase, data in json.load(fd).items():
            for rotation, alternatives in data['rotations'].items():
                for alternative, hashed in alternatives.items():
                    masks[hashed] = {
                        'case': kase,
                        'rotation': rotation,
                        'alternative': alternative,
                    }
            info[kase] = {
                'probability': data['probability'],
            }
            if data['setups']:
                setups[kase] = data['setups']


load_and_fill(OLL_PATH, OLL_MASKS, OLL_INFO, OLL_SETUPS)
load_and_fill(PLL_PATH, PLL_MASKS, PLL_INFO, PLL_SETUPS)


class CFOPAnalyser(Analyser):
    name = 'CFOP'
    step_list = ('Cross', 'F2L', 'OLL', 'PLL')
    aufs: ClassVar[dict[str, tuple[bool, bool]]] = {
        'F2L': [True, False],
        'OLL': [True, False],
        'PLL': [True, True],
    }
    norms: ClassVar[dict[str, dict[str, float]]] = {
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
        'recognition': {
            'Cross': 0.0,
            'F2L': (30.0, 40.0),
            'OLL': (10.0, 20.0),
            'PLL': (5.0, 10.0),
        },
        'execution': {
            'Cross': 100.0,
            'F2L': (60.0, 70.0),
            'OLL': (80.0, 90.0),
            'PLL': (90.0, 95.0),
        },
        'solve': {
            'recognition': (10, 20),
            'execution': (80, 100),
        },
    }

    def compute_progress(self, facelets):
        progress = 0

        for name in self.step_list[:-1]:
            if self.check_step(name, facelets):
                progress += 1
            else:
                break

        return progress, []

    def correct_summary(self, summary):
        # Fix OLL SKIP instead of F2L
        cases = []
        for info in summary:
            cases.extend(info['cases'])
            if info['increment'] > 1 and 'OLL' in info['name']:
                info['name'] = 'F2L'

        self.correct_summary_cfop(summary)

    def get_oll_case(self, facelets):
        masked = []
        for value in facelets:
            if value != 'D':
                masked.append('-')
            else:
                masked.append(value)

        masked = ''.join(masked)

        if masked in OLL_MASKS:
            return OLL_MASKS[masked]['case']

        return ''

    def get_pll_case(self, facelets):
        mask = ('0' * 9) + ('000000111' * 2) + ('0' * 9) + ('000000111' * 2)
        masked = self.build_facelets_masked(
            mask,
            facelets,
        )

        if masked in PLL_MASKS:
            return PLL_MASKS[masked]['case']

        return ''

    @cached_property
    def score(self):
        bonus = 0

        step_one = self.summary[0]
        if 'XCross' in step_one['name']:
            bonus = 2 * step_one['name'].count('X')

        malus = 0
        if 'Cross' in step_one['name']:
            cross_norm = self.norms.get('moves', {}).get(step_one['name'], 0)
            if cross_norm:
                malus += step_one['reconstruction'].metrics['htm'] - cross_norm

        for info in self.summary:
            if info['type'] != 'virtual':
                if info['post_pause'] < SECOND * 0.5:
                    bonus += 0.5
                elif info['post_pause'] < SECOND:
                    bonus += 0.25

                if info['name'] in {'OLL', 'PLL'}:
                    for auf in info['aufs']:
                        if auf:
                            malus += int(auf)

        return 20 + bonus - malus

    def correct_summary_cfop(self, summary):
        # Skipped PLL insert
        if summary[-1]['name'] != 'PLL':
            summary.append(
                {
                    'type': 'skipped',
                    'name': 'PLL',
                    'moves': Algorithm(),
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
                    'reconstruction': Algorithm(),
                    'reconstruction_timed': Algorithm(),
                    'increment': 0,
                    'cases': ['SKIP'],
                    'facelets': '',
                },
            )

        # Skipped OLL insert
        if summary[-2]['name'] != 'OLL':
            summary.insert(
                len(summary) - 1,
                {
                    'type': 'skipped',
                    'name': 'OLL',
                    'moves': Algorithm(),
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
                    'reconstruction': Algorithm(),
                    'reconstruction_timed': Algorithm(),
                    'increment': 0,
                    'cases': ['SKIP'],
                    'facelets': '',
                },
            )

        # Guess OLL/PLL cases
        for info in summary:
            if info['name'] == 'OLL':
                facelets = info['facelets']
                if facelets:
                    info['cases'] = [self.get_oll_case(facelets)]

            elif info['name'] == 'PLL':
                facelets = info['facelets']
                if facelets:
                    info['cases'] = [self.get_pll_case(facelets)]


class CF4OPAnalyser(CFOPAnalyser):
    name = 'CF4OP'
    step_list = ('Cross', 'F2L 1', 'F2L 2', 'F2L 3', 'F2L 4', 'OLL', 'PLL')
    aufs: ClassVar[dict[str, tuple[bool, bool]]] = {
        'F2L 1': [True, False],
        'F2L 2': [True, False],
        'F2L 3': [True, False],
        'F2L 4': [True, False],
        'OLL': [True, True],
        'PLL': [True, True],
    }
    norms: ClassVar[dict[str, dict[str, float]]] = {
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
        'recognition': {
            'Cross': 0.0,
            'F2L': (30.0, 40.0),
            'F2L 1': (30.0, 40.0),
            'F2L 2': (30.0, 40.0),
            'F2L 3': (30.0, 40.0),
            'F2L 4': (30.0, 40.0),
            'OLL': (10.0, 20.0),
            'PLL': (5.0, 10.0),
        },
        'execution': {
            'Cross': 100.0,
            'F2L': (60.0, 70.0),
            'F2L 1': (60.0, 70.0),
            'F2L 2': (60.0, 70.0),
            'F2L 3': (60.0, 70.0),
            'F2L 4': (60.0, 70.0),
            'OLL': (80.0, 90.0),
            'PLL': (90.0, 95.0),
        },
        'solve': {
            'recognition': (30, 40),
            'execution': (60, 70),
        },
    }

    def compute_progress(self, facelets):
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
        # Merge XCrosses
        if summary[0]['name'] == 'F2L 1':
            summary[0]['name'] = 'XCross'

        elif summary[0]['name'] == 'F2L 2':
            summary[0]['name'] = 'XXCross'

        elif summary[0]['name'] == 'F2L 3':
            summary[0]['name'] = 'XXXCross'

        elif summary[0]['name'] == 'F2L 4':
            summary[0]['name'] = 'XXXXCross'

        # Merge double F2L inserts
        cases = []
        for i, info in enumerate(summary):
            cases.extend(info['cases'])
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
                    info['cases'] = list(
                        {'FR', 'FL', 'BR', 'BL'} -
                        set(cases),
                    )

        self.correct_summary_cfop(summary)

        # Summary for F2L
        f2l = {
            'type': 'virtual',
            'name': 'F2L',
            'moves': Algorithm(),
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [0, 0],
            'total_percent': 0,
            'execution_percent': 0,
            'recognition_percent': 0,
            'step_execution_percent': 0,
            'step_recognition_percent': 0,
            'reconstruction': Algorithm(),
            'reconstruction_timed': Algorithm(),
            'increment': 0,
            'cases': [],
            'facelets': '',
        }

        f2l_steps = len(
            [
                info for info in summary
                if 'F2L ' in info['name']
             ],
        )

        insert_f2l = False
        for info in summary:
            if 'F2L ' in info['name']:
                info['type'] = 'substep'

                insert_f2l = True
                f2l['moves'].extend(info['moves'])
                f2l['times'].extend(info['times'])
                f2l['index'].extend(info['index'])
                f2l['qtm'] += info['qtm']
                f2l['total'] += info['total']
                f2l['execution'] += info['execution']
                f2l['recognition'] += info['recognition']
                f2l['post_pause'] = info['post_pause']
                if info['aufs'][0]:
                    f2l['aufs'][0] += info['aufs'][0]
                if info['aufs'][1]:
                    f2l['aufs'][1] += info['aufs'][1]
                f2l['total_percent'] += info['total_percent']
                f2l['execution_percent'] += info['execution_percent']
                f2l['recognition_percent'] += info['recognition_percent']
                f2l['step_execution_percent'] += info['step_execution_percent']
                f2l['step_recognition_percent'] += info['step_recognition_percent']  # noqa: E501
                f2l['reconstruction'].extend(info['reconstruction'])
                f2l['reconstruction_timed'].extend(info['reconstruction_timed'])

        f2l['step_execution_percent'] /= f2l_steps
        f2l['step_recognition_percent'] /= f2l_steps

        if not f2l['aufs'][0]:
            f2l['aufs'][0] = None
        if not f2l['aufs'][1]:
            f2l['aufs'][1] = None

        if insert_f2l:
            if 'F2L' not in summary[0]['name']:
                summary.insert(1, f2l)
            else:
                summary.insert(0, f2l)
