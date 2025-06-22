from contextlib import suppress
from functools import cached_property
from typing import ClassVar

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_full_moves
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.rotation import remove_final_rotations
from cubing_algs.transform.slice import reslice_moves
from cubing_algs.transform.timing import untime_moves
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_ORIENTATION
from term_timer.constants import MS_TO_NS_FACTOR

INITIAL = ''
for face in ['U', 'R', 'F', 'D', 'L', 'B']:
    INITIAL += face * 9

CENTER_PIECE = '000010000'
CROSS_PIECE  = '010010000'  # noqa: E221
LEFT_FACE    = '110110000'  # noqa: E221
RIGHT_FACE   = '011011000'  # noqa: E221
F1L_FACE     = '111010000'  # noqa: E221
F2L_FACE     = '111111000'  # noqa: E221
FULL_FACE    = '1' * 9      # noqa: E221
FULL_CUBE    = '1' * 54     # noqa: E221

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
    'F1L': {
        'mask': (
            FULL_FACE + (F1L_FACE * 2)
            + CENTER_PIECE + (F1L_FACE * 2)
        ),
        'transformations': (
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'F2L 1': {  # FR Pair
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
    'F2L 2': {  # FL Pair
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
    'F2L 3': {  # BR Pair
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
    'F2L 4': {  # BL Pair
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
            reslice_moves,
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'LL': {
        'mask': FULL_CUBE,
        'transformations': (
            reslice_moves,
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
    'RAW': {
        'mask': FULL_CUBE,
        'transformations': (
            reslice_moves,
            degrip_full_moves,
            remove_final_rotations,
            optimize_double_moves,
        ),
    },
}


class Analyser:
    name = ''
    step_list: tuple[str] = ()
    norms: ClassVar[dict[str, dict[str, float]]] = {}

    def __init__(self, scramble, solution):
        self.scramble = scramble
        self.solution = solution

        self.duration = (
            self.solution[-1].timed - self.solution[0].timed
        ) * MS_TO_NS_FACTOR

        self.steps = self.split_steps()
        self.summary = self.summarize()

    def split_steps(self):
        cube = VCube()
        facelets = cube.rotate(self.scramble)

        steps = {}
        cases = []
        progress = 0
        step_moves = []

        for move_index, move in enumerate(self.solution):
            current_progress, current_cases = self.compute_progress(cube.state)

            if current_progress > progress:
                step_name = self.step_list[current_progress - 1]
                cleaned_cases = list(set(current_cases) - set(cases))

                steps[step_name] = {
                    'moves': step_moves.copy(),
                    'increment': current_progress - progress,
                    'cases': cleaned_cases,
                    'facelets': facelets,
                }
                step_moves = []
                facelets = cube.state
                progress = current_progress
                cases.extend(cleaned_cases)

            step_moves.append(move_index)
            cube.rotate(move.untimed)

        step_name = self.step_list[progress]
        steps[step_name] = {
            'moves': step_moves.copy(),
            'increment': 1,
            'cases': [],
            'facelets': facelets,
        }

        return steps

    def compute_progress(self):
        raise NotImplementedError

    def summarize(self):
        summary = []

        for step in self.step_list:
            if step not in self.steps:
                continue

            info = self.steps[step]
            step_moves = info['moves']

            moves = [self.solution[i] for i in step_moves]
            times = [self.solution[i].timed for i in step_moves]

            ante_time = 0
            if step_moves[0]:
                ante_time = self.solution[step_moves[0] - 1].timed

            post_time = 0
            with suppress(IndexError):
                post_time = self.solution[step_moves[-1] + 1].timed

            execution = (
                self.solution[step_moves[-1]].timed
                - self.solution[step_moves[0]].timed
            ) * MS_TO_NS_FACTOR
            recognition = (
                self.solution[step_moves[0]].timed
                - ante_time
            ) * MS_TO_NS_FACTOR
            post_pause = max(
                (
                    post_time
                    - self.solution[step_moves[-1]].timed
                ) * MS_TO_NS_FACTOR,
                0,
            )

            total = execution + recognition

            reconstruction = CUBE_ORIENTATION + moves
            reconstruction = reconstruction.transform(
                *STEPS_CONFIG[step]['transformations'],
                to_fixpoint=True,
            )

            summary.append(
                {
                    'type': 'step',
                    'name': step,
                    'moves': moves,
                    'times': times,
                    'index': step_moves,
                    'qtm': len(moves),
                    'total': total,
                    'execution': execution,
                    'recognition': recognition,
                    'post_pause': post_pause,
                    'total_percent': (total / self.duration) * 100,
                    'execution_percent': (execution / self.duration) * 100,
                    'recognition_percent': (recognition / self.duration) * 100,
                    'step_execution_percent': (execution / total) * 100,
                    'step_recognition_percent': (recognition / total) * 100,
                    'reconstruction': reconstruction.transform(untime_moves),
                    'reconstruction_timed': reconstruction,
                    'increment': info['increment'],
                    'cases': info['cases'],
                    'facelets': info['facelets'],
                },
            )

        self.correct_summary(summary)

        return summary

    def correct_summary(self, summary):
        pass

    def normalize_value(self, metric, name, value, default,
                        *, threshold=1.2):
        norm = self.norms.get(metric, {}).get(name)
        if not norm:
            return default

        if isinstance(norm, (int | float)):
            if value <= norm:
                return 'success'

            if value >= norm * threshold:
                return 'warning'

            return 'caution'

        if isinstance(norm, (tuple | list)) and len(norm) == 2:
            threshold_down, threshold_up = norm

            if threshold_down <= value <= threshold_up:
                return 'success'

            if (
                    value < threshold_down * (2 - threshold)
                    or value > threshold_up * threshold
            ):
                return 'warning'

            return 'caution'

        return default

    @cached_property
    def score(self):
        return 20

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
