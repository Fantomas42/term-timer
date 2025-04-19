from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_m_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.formatter import format_duration
from term_timer.magic_cube import Cube

CENTER_PIECE = '000010000'
CROSS_PIECE  = '010010000'
LEFT_FACE    = '110110000'
RIGHT_FACE   = '011011000'
F2L_FACE     = '111111000'
FULL_FACE    = '1' * 9
FULL_CUBE    = '1' * 54

INITIAL = 'U' * 9 + 'R' * 9 + 'F' * 9 + 'D' * 9 + 'L' * 9 + 'B' * 9

STEPS_CONFIG = {
    'Cross': {
        'mask': (
            '010111010' + (CROSS_PIECE * 2)
            + CENTER_PIECE + (CROSS_PIECE * 2)
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L-1': {  # FR Pair
        'mask':  (
            '010111011' + LEFT_FACE + RIGHT_FACE
            + CENTER_PIECE + CROSS_PIECE + CROSS_PIECE
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L-2': {  # FL Pair
        'mask': (
            '010111110' + CROSS_PIECE + LEFT_FACE
            + CENTER_PIECE + RIGHT_FACE + CROSS_PIECE
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L-3': {  # BR Pair
        'mask':  (
            '011111010' + RIGHT_FACE + CROSS_PIECE
            + CENTER_PIECE + CROSS_PIECE + LEFT_FACE
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L-4': {  # BL Pair
        'mask':  (
            '110111010' + CROSS_PIECE + CROSS_PIECE
            + CENTER_PIECE + LEFT_FACE + RIGHT_FACE
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L': {
        'mask': (
            FULL_FACE + (F2L_FACE * 2)
            + CENTER_PIECE + (F2L_FACE * 2)
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'OLL': {
        'mask': (
            FULL_FACE + (F2L_FACE * 2)
            + FULL_FACE + (F2L_FACE * 2)
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'PLL': {
        'mask': FULL_CUBE,
        'transformations': (
            reslice_m_moves,
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
}


class Analyser:
    name = ''
    step_list = []

    def __init__(self, scramble, move_times):
        self.scramble = scramble
        self.move_times = move_times

        self.steps = {}
        for step in self.step_list:
            self.steps[step] = {
                'moves': [],
            }

        self.duration = (
            self.move_times[-1][1] - self.move_times[0][1]
        ) * 1_000_000

        self.split_steps()

    def split_steps(self):
        cube = Cube(3)
        cube.rotate(self.scramble)

        progress = 0
        step_moves = []

        for move, time in self.move_times:
            current_progress = self.compute_progress(cube)

            if current_progress > progress:
                step_name = self.step_list[current_progress - 1]

                progress = current_progress
                self.steps[step_name]['moves'] = step_moves.copy()
                step_moves = []

            step_moves.append((move, time))
            cube.rotate(move)

        step_name = self.step_list[-1]
        self.steps[step_name]['moves'] = step_moves.copy()

    def compute_progress(self):
        raise NotImplementedError

    @staticmethod
    def build_facelets_masked(mask: str, facelets: str) -> str:
        masked = []
        for i, value in enumerate(facelets):
            if mask[i] == '0':
                masked.append('-')
            else:
                masked.append(value)

        return ''.join(masked)

    def check_step(self, step, facelets):
        matching = self.build_facelets_masked(
            STEPS_CONFIG[step]['mask'],
            INITIAL,
        )
        return matching == self.build_facelets_masked(
            STEPS_CONFIG[step]['mask'],
            facelets,
        )

    # TODO(me): cache
    def step_info(self, step):
        infos = self.steps[step]

        if not infos['moves']:
            return {}

        step_index = self.step_list.index(step)
        previous_move = ('', 0)
        if step_index:
            i = 1
            previous_move = self.steps[self.step_list[step_index - i]]['moves'][-1]

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
            *STEPS_CONFIG[step]['transformations'],
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

        for step in self.step_list:
            infos = self.step_info(step)
            if not infos:
                continue
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

        for step in self.step_list:
            infos = self.step_info(step)
            recons += f'{ infos["reconstruction"]!s }'

        return parse_moves(recons)


class CFOPAnalyser(Analyser):
    name = 'CFOP'
    step_list = ('Cross', 'F2L', 'OLL', 'PLL')

    def compute_progress(self, cube):
        progress = 0
        facelets = cube.as_twophase_facelets

        for name in self.step_list:
            if self.check_step(name, facelets):
                progress += 1
            else:
                break

        return progress


class CF4OPAnalyser(Analyser):
    name = 'CF4OP'
    step_list = ('Cross', 'F2L-1', 'F2L-2', 'F2L-3', 'F2L-4', 'OLL', 'PLL')

    def compute_progress(self, cube):
        facelets = cube.as_twophase_facelets

        if not self.check_step('Cross', facelets):
            return 0

        if not self.check_step('OLL', facelets):
            return 1 + int(
                self.check_step('F2L-1', facelets),
            ) + int(
                self.check_step('F2L-2', facelets),
            ) + int(
                self.check_step('F2L-3', facelets),
            ) + int(
                self.check_step('F2L-4', facelets),
            )

        return 6
