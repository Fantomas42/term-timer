from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_m_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.formatter import format_duration
from term_timer.magic_cube import Cube


class CFOPAnalyser:
    STEPS = ('cross', 'f2l', 'oll', 'pll')
    STEPS_CONFIG = {
        'cross': {
            'mask': '010111010' + '000010000' * 5,
            'match': '-U-UUU-U-----R--------F--------D--------L--------B----',
            'transformations': (
                degrip_full_moves,
                remove_final_rotations,
                optimize_double_moves,
            ),
        },
        'f2l': {
            'mask': '111111111' + ('111111000' * 2) + '000000000' + ('111111000' * 2),
            'match': 'UUUUUUUUURRRRRR---FFFFFF------------LLLLLL---BBBBBB---',
            'transformations': (
                degrip_full_moves,
                remove_final_rotations,
                optimize_double_moves,
            ),
        },
        'oll': {
            'mask': '111111111' + ('111111000' * 2) + '111111111' + ('111111000' * 2),
            'match': 'UUUUUUUUURRRRRR---FFFFFF---DDDDDDDDDLLLLLL---BBBBBB---',
            'transformations': (
                degrip_full_moves,
                remove_final_rotations,
                optimize_double_moves,
            ),
        },
        'pll': {
            'mask': '1' * 54,
            'match': 'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB',
            'transformations': (
                reslice_m_moves,
                degrip_full_moves,
                remove_final_rotations,
                optimize_double_moves,
            ),
        },
    }

    def __init__(self, scramble, move_times):
        self.scramble = scramble
        self.move_times = move_times

        self.steps = {}
        for step in self.STEPS:
            self.steps[step] = {
                'moves': [],
                'comments': [],
            }

        self.duration = (
            self.move_times[-1][1] - self.move_times[0][1]
        ) * 1_000_000

        self.split_steps()

    def split_steps(self):
        cube = Cube(3)
        cube.rotate(self.scramble)

        move_index = 0
        current_step = self.STEPS[0]
        step_moves = []

        while not cube.is_done():
            step_index = self.STEPS.index(current_step)

            for step in self.STEPS[step_index:]:
                step_passed = self.check_step(step, cube)
                if step_passed:
                    self.steps[step]['moves'] = step_moves.copy()
                    current_step = self.STEPS[step_index + 1]
                    step_moves = []
                else:
                    break

            step_moves.append(self.move_times[move_index])
            cube.rotate(self.move_times[move_index][0])
            move_index += 1

        self.steps[current_step]['moves'] = step_moves.copy()

    @staticmethod
    def build_facelets_masked(mask: str, facelets: str) -> str:
        masked = []
        for i, value in enumerate(facelets):
            if mask[i] == '0':
                masked.append('-')
            else:
                masked.append(value)

        return ''.join(masked)

    def check_step(self, step, cube):
        return self.STEPS_CONFIG[step]['match'] == self.build_facelets_masked(
            self.STEPS_CONFIG[step]['mask'],
            cube.as_twophase_facelets,
        )

    # TODO(me): cache
    def step_info(self, step):
        infos = self.steps[step]

        step_index = self.STEPS.index(step)
        if not step_index:
            previous_move = ('', 0)
        else:
            previous_move = self.steps[self.STEPS[step_index - 1]]['moves'][-1]

        execution = 0
        inspection = 0
        try:
            execution = (infos['moves'][-1][1] - infos['moves'][0][1]) * 1_000_000
            inspection = (infos['moves'][0][1] - previous_move[1]) * 1_000_000
        except IndexError:
            pass

        moves = [m[0] for m in infos['moves']]
        times = [m[1] for m in infos['moves']]

        recons = parse_moves([CUBE_ORIENTATION] + moves).transform(
            *self.STEPS_CONFIG[step]['transformations'],
            to_fixpoint=True,
        )

        return {
            'reconstruction': recons,
            'moves': moves,
            'times': times,
            'inspection': inspection,
            'execution': execution,
            'total': inspection + execution,
        }

    @property
    def reconstruction_detailed(self):
        recons = ''

        if CUBE_ORIENTATION:
            recons += f'{ CUBE_ORIENTATION } // Orientation\n'

        for step in self.STEPS:
            infos = self.step_info(step)
            recons += (
                f'{ infos["reconstruction"]!s } // '
                f'{ step.title() }  '
                f'Insp: { format_duration(infos["inspection"]) }s '
                f'Exec: { format_duration(infos["execution"]) }s '
                f'Moves: { len(infos["reconstruction"]) }\n'
            )

        return recons

    @property
    def reconstruction(self):
        recons = ''

        for step in self.STEPS:
            infos = self.step_info(step)
            recons += f'{ infos["reconstruction"]!s }'

        return parse_moves(recons)
