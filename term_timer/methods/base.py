from collections.abc import Callable
from collections.abc import Iterable
from contextlib import suppress
from functools import cached_property
from typing import Any
from typing import ClassVar
from typing import Literal
from typing import TypedDict

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import INITIAL_STATE
from cubing_algs.masks import CENTERS_MASK
from cubing_algs.masks import CROSS_MASK
from cubing_algs.masks import F2L_BL_MASK
from cubing_algs.masks import F2L_BR_MASK
from cubing_algs.masks import F2L_FL_MASK
from cubing_algs.masks import F2L_FR_MASK
from cubing_algs.masks import F2L_MASK
from cubing_algs.masks import FULL_MASK
from cubing_algs.masks import L1_MASK
from cubing_algs.masks import OLL_MASK
from cubing_algs.masks import facelets_masked
from cubing_algs.masks import union_masks
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.vcube import VCube

from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.methods.cases import CASES_MASKS
from term_timer.methods.cases import CaseMaskInfo
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves
from term_timer.transform import reorient_moves
from term_timer.triggers import DEFAULT_TRIGGERS

AUF_MOVE = 'D'  # Because actually AUF is based on a URFDLB cube and moves

CROSS_CENTER_MASK = union_masks(CROSS_MASK, CENTERS_MASK)


class StepInfo(TypedDict):
    """
    Information about a single step during solve analysis.
    """
    moves: list[int]
    increment: int
    case_infos: list[str]
    facelets: str


class StepSummary(TypedDict):
    """
    Summary information for a completed step.
    """
    type: Literal['step', 'skipped', 'substep', 'virtual']
    name: str
    moves: Algorithm
    moves_reoriented: Algorithm
    moves_humanized: Algorithm
    moves_prettified: Algorithm
    times: list[float]
    index: list[int]
    qtm: int
    total: int
    execution: int
    recognition: int
    post_pause: int
    aufs: list[int | None]
    total_percent: float
    execution_percent: float
    recognition_percent: float
    step_execution_percent: float
    step_recognition_percent: float
    increment: int
    case: str
    case_infos: list[str]
    facelets: str


class StepConfig(TypedDict, total=False):
    """Configuration for a solving step."""
    mask: str
    triggers: list[str]
    optimizers: list[Callable[[Algorithm], Algorithm]]


STEPS_CONFIG: dict[str, StepConfig] = {
    'Cross': {
        'mask': CROSS_CENTER_MASK,
    },
    'F1L': {
        'mask': union_masks(CENTERS_MASK, L1_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'F2L': {
        'mask': union_masks(CENTERS_MASK, F2L_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'F2L 1': {  # FR Pair
        'mask': union_masks(CROSS_CENTER_MASK, F2L_FR_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'F2L 2': {  # FL Pair
        'mask': union_masks(CROSS_CENTER_MASK, F2L_FL_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'F2L 3': {  # BR Pair
        'mask': union_masks(CROSS_CENTER_MASK, F2L_BR_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'F2L 4': {  # BL Pair
        'mask': union_masks(CROSS_CENTER_MASK, F2L_BL_MASK),
        'triggers': DEFAULT_TRIGGERS,
    },
    'OLL': {
        'mask': union_masks(OLL_MASK, F2L_MASK),
        'triggers': DEFAULT_TRIGGERS,
        'optimizers': [remove_auf_moves],
    },
    'PLL': {
        'mask': FULL_MASK,
        'triggers': DEFAULT_TRIGGERS,
        'optimizers': [remove_auf_moves],
    },
    'LL': {
        'mask': FULL_MASK,
        'triggers': DEFAULT_TRIGGERS,
        'optimizers': [remove_auf_moves],
    },
    'RAW': {
        'mask': FULL_MASK,
        'triggers': DEFAULT_TRIGGERS,
    },
}


class FaceletAnalyser:

    def get_step_case(self, step: str, facelets: str,
                      encoder: Callable[[str], str]) -> str:
        encoded = encoder(facelets)

        case_mask: CaseMaskInfo | None = CASES_MASKS[step].get(encoded)
        if case_mask:
            return case_mask['case']

        return ''

    def check_step(self, step: str, facelets: str) -> bool:
        mask = get_step_config(step, 'mask')

        matching = facelets_masked(
            INITIAL_STATE, mask,
        )

        return matching == facelets_masked(
            facelets, mask,
        )


class Analyser(FaceletAnalyser):
    name = ''
    step_list: tuple[str, ...] = ()
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {}
    aufs: ClassVar[dict[str, list[bool]]] = {}
    aggregate: ClassVar[dict[str, int]] = {}

    def __init__(self, scramble: Algorithm, solution: Algorithm,
                 orientation_moves: Algorithm):
        self.scramble = scramble
        self.solution = solution
        self.orientation_moves = orientation_moves

        self.duration = (
            self.get_solution_move_time(-1) - self.get_solution_move_time(0)
        ) * MS_TO_NS_FACTOR

        self.steps = self.split_steps()
        self.summary = self.summarize()

    def get_solution_move_time(self, index: int) -> int:
        """
        Get timing value for a move in the solution.
        """
        return self.solution[index].timed

    def split_steps(self) -> dict[str, StepInfo]:
        cube = VCube()
        facelets = cube.rotate(self.scramble)

        steps: dict[str, StepInfo] = {}
        progress = 0
        case_infos: list[str] = []
        step_moves: list[int] = []

        for move_index, move in enumerate(self.solution):
            current_progress, current_case_infos = self.compute_progress(
                cube.state,
            )

            if current_progress > progress:
                step_name = self.step_list[current_progress - 1]
                cleaned_case_infos = list(
                    set(current_case_infos) - set(case_infos),
                )

                steps[step_name] = {
                    'moves': step_moves.copy(),
                    'increment': current_progress - progress,
                    'case_infos': cleaned_case_infos,
                    'facelets': facelets,
                }
                step_moves = []
                facelets = cube.state
                progress = current_progress
                case_infos.extend(cleaned_case_infos)

            step_moves.append(move_index)
            cube.rotate(move.untimed)

        step_name = self.step_list[progress]
        steps[step_name] = {
            'moves': step_moves.copy(),
            'increment': 1,
            'case_infos': [],
            'facelets': facelets,
        }

        return steps

    def compute_progress(self, facelets: str) -> tuple[int, list[str]]:
        raise NotImplementedError

    def summarize(self) -> list[StepSummary]:
        summary: list[StepSummary] = []

        for step in self.step_list:
            if step not in self.steps:
                continue

            info = self.steps[step]
            step_moves = info['moves']

            if not step_moves:
                continue

            moves = parse_moves([self.solution[i] for i in step_moves])
            times = [float(self.get_solution_move_time(i)) for i in step_moves]

            ante_time = 0
            if step_moves[0]:
                ante_time = self.get_solution_move_time(step_moves[0] - 1)

            post_time = 0
            with suppress(IndexError):
                post_time = self.get_solution_move_time(step_moves[-1] + 1)

            execution = (
                self.get_solution_move_time(step_moves[-1])
                - self.get_solution_move_time(step_moves[0])
            ) * MS_TO_NS_FACTOR
            recognition = (
                self.get_solution_move_time(step_moves[0]) - ante_time
            ) * MS_TO_NS_FACTOR
            post_pause = max(
                (post_time - self.get_solution_move_time(step_moves[-1]))
                * MS_TO_NS_FACTOR,
                0,
            )

            total = execution + recognition

            reorientation = reorient_moves(self.orientation_moves, moves)
            humanization = humanize_moves(reorientation)
            prettyfication = prettify_moves(humanization)

            aufs = self.get_aufs(step, moves)

            summary.append(
                {
                    'type': 'step',
                    'name': step,
                    'moves': moves,
                    'moves_reoriented': reorientation,
                    'moves_humanized': humanization,
                    'moves_prettified': prettyfication,
                    'times': times,
                    'index': step_moves,
                    'qtm': len(moves),
                    'total': total,
                    'execution': execution,
                    'recognition': recognition,
                    'post_pause': post_pause,
                    'aufs': aufs,
                    'total_percent': (total / self.duration) * 100,
                    'execution_percent': (execution / self.duration) * 100,
                    'recognition_percent': (recognition / self.duration) * 100,
                    'step_execution_percent': (execution / total) * 100,
                    'step_recognition_percent': (recognition / total) * 100,
                    'increment': info['increment'],
                    'case': '',
                    'case_infos': info['case_infos'],
                    'facelets': info['facelets'],
                },
            )

        self.correct_summary(summary)

        return summary

    def get_aufs(self, name: str, moves: Algorithm) -> list[int | None]:
        pre_auf, post_auf = None, None
        pre, post = self.aufs.get(name, [False, False])

        if pre and len(moves.metrics.generators) > 1:
            pre_auf = self.get_auf(moves, 'pre')

        if post:
            post_auf = self.get_auf(moves, 'post')

        return [pre_auf, post_auf]

    def get_auf(self, moves: Algorithm, mode: str) -> int:
        auf = 0

        moves_iter: Iterable[Move] = (
            reversed(moves)
            if mode == 'post' else moves
        )

        for move in moves_iter:
            if move[0] == AUF_MOVE:
                auf += 1
            else:
                break

        return auf

    def correct_summary(self, summary: list[StepSummary]) -> None:
        pass

    def normalize_value(self, metric: str, name: str, value: float,
                        default: str, *, threshold: float = 1.2) -> str:
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
    def score(self) -> float:
        return 20


def get_step_config(step_name: str, value: str, default: Any = None) -> Any:
    return STEPS_CONFIG.get(step_name, {}).get(value, default)
