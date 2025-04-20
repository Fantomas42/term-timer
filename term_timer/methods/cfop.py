from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_m_moves

from term_timer.config import CUBE_ORIENTATION
from term_timer.formatter import format_duration
from term_timer.magic_cube import Cube

TO_NS = 1_000_000

CENTER_PIECE = '000010000'
CROSS_PIECE  = '010010000'  # noqa: E221
LEFT_FACE    = '110110000'  # noqa: E221
RIGHT_FACE   = '011011000'  # noqa: E221
F2L_FACE     = '111111000'  # noqa: E221
FULL_FACE    = '1' * 9      # noqa: E221
FULL_CUBE    = '1' * 54     # noqa: E221

INITIAL = ''
for face in ['U', 'R', 'F', 'D', 'L', 'B']:
    INITIAL += face * 9

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
    step_list: tuple[str] = ()

    def __init__(self, scramble, move_times):
        self.scramble = scramble

        self.moves = []
        self.times = []
        for move_time in move_times:
            self.moves.append(move_time[0])
            self.times.append(move_time[1])

        self.duration = (
            self.times[-1] - self.times[0]
        ) * TO_NS

        self.steps = self.split_steps()
        self.summary = self.summarize()

    def split_steps(self):
        cube = Cube(3)
        cube.rotate(self.scramble)

        steps = {}
        progress = 0
        step_moves = []

        for move_index, move in enumerate(self.moves):
            current_progress = self.compute_progress(cube)

            if current_progress > progress:
                step_name = self.step_list[current_progress - 1]

                progress = current_progress
                steps[step_name] = step_moves.copy()
                step_moves = []

            step_moves.append(move_index)
            cube.rotate(move)

        step_name = self.step_list[-1]
        steps[step_name] = step_moves.copy()

        return steps

    def compute_progress(self):
        raise NotImplementedError

    def summarize(self):
        summary = []

        for step in self.step_list:
            if step not in self.steps:
                continue

            step_moves = self.steps[step]

            moves = [self.moves[i] for i in step_moves]
            times = [self.times[i] for i in step_moves]

            ante_time = 0
            if step_moves[0]:
                ante_time = self.times[step_moves[0] - 1]

            execution = (self.times[step_moves[-1]] - self.times[step_moves[0]]) * TO_NS
            inspection = (self.times[step_moves[0]] - ante_time) * TO_NS
            total = execution + inspection

            reconstruction = parse_moves([CUBE_ORIENTATION, *moves]).transform(
                *STEPS_CONFIG[step]['transformations'],
                to_fixpoint=True,
            )

            summary.append(
                {
                    'type': 'step',
                    'name': step,
                    'moves': moves,
                    'times': times,
                    'total': total,
                    'execution': execution,
                    'inspection': inspection,
                    'total_percent': (total / self.duration) * 100,
                    'execution_percent': (execution / self.duration) * 100,
                    'inspection_percent': (inspection / self.duration) * 100,
                    'reconstruction': reconstruction,
                    # + Missed moves
                    # + Case detection
                    # + Pair name
                },
            )

        self.correct_summary(summary)

        return summary

    def correct_summary(self):
        pass

    @property
    def reconstruction_detailed(self):
        recons = ''

        if CUBE_ORIENTATION:
            recons += f'{ CUBE_ORIENTATION } // Orientation\n'

        for info in self.summary:
            if info['type'] != 'virtual':
                recons += (
                    f'{ info["reconstruction"]!s } // '
                    f'{ info["name"] } '
                    f'Insp: { format_duration(info["inspection"]) }s '
                    f'Exec: { format_duration(info["execution"]) }s '
                    f'Moves: { len(info["reconstruction"]) }\n'
                )

        return recons

    @property
    def reconstruction(self):
        recons = ''

        for info in self.summary:
            if info['type'] != 'virtual':
                recons += f'{ info["reconstruction"]!s } '

        return parse_moves(recons)

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

    def correct_summary(self, summary):
        if summary[0]['name'] == 'F2L-1':
            summary[0]['name'] = 'XCross'

        elif summary[0]['name'] == 'F2L-2':
            summary[0]['name'] = 'XXCross'

        elif summary[0]['name'] == 'F2L-3':
            summary[0]['name'] = 'XXXCross'

        elif summary[0]['name'] == 'F2L-4':
            summary[0]['name'] = 'XXXXCross'

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
        for info in summary:
            if 'F2L-' in info['name']:
                info['type'] = 'substep'

                f2l['moves'].extend(info['moves'])
                f2l['times'].extend(info['times'])
                f2l['total'] += info['total']
                f2l['execution'] += info['execution']
                f2l['inspection'] += info['inspection']
                f2l['total_percent'] += info['total_percent']
                f2l['execution_percent'] += info['execution_percent']
                f2l['inspection_percent'] += info['inspection_percent']
                f2l['reconstruction'].extend(info['reconstruction'])

        summary.insert(1, f2l)
