"""Base classes for solving method analysis and step detection."""
from collections.abc import Callable
from collections.abc import Iterable
from contextlib import suppress
from functools import cached_property
from functools import lru_cache
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.constants import OPPOSITE_FACES
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
from cubing_algs.parsing import parse_moves
from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3
from cubing_algs.transform.auf import remove_auf_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.transform.rotation import remove_rotations
from cubing_algs.transform.translate import translate_moves
from cubing_algs.vcube import VCube

from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.methods.annotations import CaseMaskInfo
from term_timer.methods.annotations import StepConfig
from term_timer.methods.annotations import StepInfo
from term_timer.methods.annotations import StepSummary
from term_timer.methods.masks import CASES_MASKS
from term_timer.orientation import get_orientation_moves
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves
from term_timer.triggers import DEFAULT_TRIGGERS

if TYPE_CHECKING:
    from cubing_algs.move import Move

CROSS_CENTER_MASK: Final = union_masks(CROSS_MASK, CENTERS_MASK)


STEPS_CONFIG: Final[dict[str, StepConfig]] = {
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
    """
    Analyzes cube state based on facelet representation.

    Provides methods to reorient cube states, check step completion, and
    identify solving method cases based on facelet patterns.
    """

    @staticmethod
    def reorient(state: str, orientation_faces: str,
                 *, offset: bool = False) -> str:
        """
        Transform cube state to match a target orientation.

        Rotates the cube state to align with the specified orientation
        faces, optionally applying a invert transformation for offset
        calculations.

        Args:
            state: 54-character facelet string representing cube state.
            orientation_faces: Two-character string specifying bottom and
                front faces (e.g., 'UF' for white bottom, green front).
            offset: Whether to invert the orientation moves for mask
                alignment.

        Returns:
            Reoriented 54-character facelet string.

        """
        top_face = OPPOSITE_FACES[orientation_faces[0]]
        orientation = f'{ top_face }{ orientation_faces[1] }'

        moves = get_orientation_moves(orientation)

        if not moves:
            return state

        if offset:
            moves = invert_moves(moves)

        cube = VCube(state, size=3, check=False)
        cube.rotate(moves)

        return cube.state

    def get_step_case(self, step: str, facelets: str,
                      orientation_faces: str,
                      encoder: Callable[[str], str]) -> str:
        """
        Identify the solving case for a given step based on facelets.

        Reorients the cube state and encodes it to match against known
        case patterns for the specified solving step.

        Args:
            step: Name of the solving step (e.g., 'OLL', 'PLL').
            facelets: Current 54-character facelet string.
            orientation_faces: Two-character orientation specification.
            encoder: Function that encodes facelet string into case key.

        Returns:
            Case name if found in database, empty string otherwise.

        """
        facelets = self.reorient(facelets, orientation_faces, offset=False)

        encoded = encoder(facelets)

        case_mask: CaseMaskInfo | None = CASES_MASKS[step].get(encoded)
        if case_mask:
            return case_mask['case']

        return ''

    @lru_cache  # noqa: B019
    def matching_mask(self, step: str,
                      orientation_faces: str) -> tuple[str, str]:
        """
        Return matching mask and oriented mask for checking step.

        Get the step's mask and reoriente it from orientation faces,
        then prepare matching mask.
        Use lru_cache to optimize repetitive calls.

        Args:
            step: Name of the solving step to check.
            orientation_faces: Two-character orientation specification.

        Returns:
            The matching mask and the mask oriented.

        """
        mask = get_step_config(step, 'mask')

        mask = self.reorient(mask, orientation_faces, offset=True)

        matching_mask = facelets_masked(
            SOLVED_FACELETS_3x3x3, mask,
        )

        return matching_mask, mask

    def check_step(self, step: str, facelets: str,
                   orientation_faces: str) -> bool:
        """
        Verify if a solving step has been completed.

        Compares the current cube state against the expected state for
        step completion using the step's configured facelet mask.

        Args:
            step: Name of the solving step to check.
            facelets: Current 54-character facelet string.
            orientation_faces: Two-character orientation specification.

        Returns:
            True if step is completed, False otherwise.

        """
        matching_mask, mask = self.matching_mask(step, orientation_faces)

        return matching_mask == facelets_masked(
            facelets, mask,
        )


class Analyser(FaceletAnalyser):
    """
    Analyzes solve performance by breaking it into method-specific steps.

    Processes scramble and solution sequences to identify step boundaries,
    calculate timing metrics, recognize cases, and generate comprehensive
    solve statistics for training and analysis.

    Attributes:
        name: Human-readable name of the solving method.
        step_list: Ordered tuple of step names in the solving sequence.
        norms: Performance benchmarks for normalizing metrics.
        aufs: Configuration for AUF (adjustment U face) detection per step.
        aggregate: Aggregation rules for combining step statistics.

    """

    name = ''
    step_list: tuple[str, ...] = ()
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {}
    aufs: ClassVar[dict[str, list[bool]]] = {}
    aggregate: ClassVar[dict[str, int]] = {}

    def __init__(self, scramble: Algorithm, solution: Algorithm,
                 orientation_faces: str,
                 orientation_moves: Algorithm,
                 *, disable_rotations: bool) -> None:
        """
        Initialize analyser with solve data and orientation.

        Args:
            scramble: Algorithm used to scramble the cube.
            solution: Complete algorithm sequence solving the scramble.
            orientation_faces: Two-character bottom/front face orientation.
            orientation_moves: Rotation moves to achieve target orientation.
            disable_rotations: Disable rotations on analyse.

        """
        self.scramble = scramble
        self.solution = solution

        if disable_rotations and self.solution.has_rotations:
            self.solution = self.solution.transform(
                remove_rotations,
            )

        self.orientation_faces = orientation_faces
        self.orientation_moves = orientation_moves

        self.duration = (
            self.get_solution_move_time(-1) - self.get_solution_move_time(0)
        ) * MS_TO_NS_FACTOR

        self.steps = self.split_steps()
        self.summary = self.summarize()

    def get_solution_move_time(self, index: int) -> int:
        """
        Get the timestamp of a move in the solution sequence.

        Args:
            index: Zero-based position of the move in the solution.

        Returns:
            Timestamp in milliseconds for the specified move.

        """
        return self.solution[index].timed

    def split_steps(self) -> dict[str, StepInfo]:
        """
        Divide the solution into distinct solving method steps.

        Simulates cube execution move-by-move, detecting step completion
        by checking facelet patterns. Associates each move with its
        corresponding step and captures the cube state at transitions.

        Returns:
            Dictionary mapping step names to their move indices, case info,
            and facelet states at step start.

        """
        cube = VCube(size=3)
        facelets = cube.rotate(self.scramble)

        steps: dict[str, StepInfo] = {}
        progress = 0
        case_infos: list[str] = []
        step_moves: list[int] = []

        for move_index, move in enumerate(self.solution):
            current_progress, current_case_infos = self.compute_progress(
                cube.state, progress,
            )

            if current_progress > progress:
                step_name = self.step_list[current_progress - 1]
                cleaned_case_infos = sorted(
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
            if move.is_face_move:
                cube.rotate(move.untimed)

        step_name = self.step_list[progress]
        steps[step_name] = {
            'moves': step_moves.copy(),
            'increment': 1,
            'case_infos': [],
            'facelets': facelets,
        }

        return steps

    def compute_progress(self, facelets: str,
                         progress: int) -> tuple[int, list[str]]:
        """
        Calculate solve progress and identify cases at current state.

        Must be implemented by subclasses to define method-specific logic
        for detecting which steps have been completed and what cases are
        present in the current cube state.

        Args:
            facelets: Current 54-character facelet string.
            progress: Number of steps completed so far.

        Returns:
            Tuple of (new progress count, list of detected case names).

        Raises:
            NotImplementedError: Must be overridden by subclass.

        """
        raise NotImplementedError

    def summarize(self) -> list[StepSummary]:
        """
        Generate comprehensive statistics for each step in the solve.

        Calculates timing metrics (execution, recognition, pauses), move
        transformations (reoriented, humanized, prettified), percentage
        breakdowns, and AUF detection for all detected steps.

        Returns:
            List of step summaries with timing and analysis data.

        """
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

            reorientation = translate_moves(self.orientation_moves)(moves)
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
                    'step_execution_percent': (
                        (execution / total) * 100 if total > 0 else 100.0
                    ),
                    'step_recognition_percent': (
                        (recognition / total) * 100 if total > 0 else 0.0
                    ),
                    'increment': info['increment'],
                    'case': '',
                    'case_infos': info['case_infos'],
                    'facelets': info['facelets'],
                },
            )

        self.correct_summary(summary)

        return summary

    def get_aufs(self, name: str, moves: Algorithm) -> list[int | None]:
        """
        Detect pre-AUF and post-AUF moves for a step's algorithm.

        AUF (Adjustment U Face) moves are U-layer rotations before or
        after the main algorithm. Detection is configured per step.

        Args:
            name: Step name to check AUF configuration for.
            moves: Algorithm sequence to analyze.

        Returns:
            List containing [pre-AUF count or None, post-AUF count or None].

        """
        pre_auf, post_auf = None, None
        pre, post = self.aufs.get(name, [False, False])

        if pre and len(moves.metrics.generators) > 1:
            pre_auf = self.get_auf(moves, 'pre')

        if post:
            post_auf = self.get_auf(moves, 'post')

        return [pre_auf, post_auf]

    def get_auf(self, moves: Algorithm, mode: str) -> int:
        """
        Count consecutive U-face moves at the start or end of algorithm.

        Args:
            moves: Algorithm sequence to analyze.
            mode: Either 'pre' for start or 'post' for end of sequence.

        Returns:
            Number of consecutive U-face moves found in QTM.

        """
        auf_move = self.orientation_faces[0]
        auf = 0

        moves_iter: Iterable[Move] = (
            reversed(moves)
            if mode == 'post' else moves
        )

        for move in moves_iter:
            if move[0] == auf_move:
                auf += 1
            else:
                break

        return auf

    def correct_summary(self, summary: list[StepSummary]) -> None:
        """
        Apply method-specific corrections to step summaries.

        Hook for subclasses to adjust summary data based on specific
        solving method requirements. Default implementation does nothing.

        Args:
            summary: List of step summaries to potentially modify in-place.

        """

    @staticmethod
    def create_skipped_summary(name: str) -> StepSummary:
        """
        Create a skipped StepSummary.

        Args:
            name: Name of the step skipped.

        Returns:
            StepSummary with skipped data.

        """
        return {
            'type': 'skipped',
            'name': name,
            'moves': Algorithm(),
            'moves_reoriented': Algorithm(),
            'moves_humanized': Algorithm(),
            'moves_prettified': Algorithm(),
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
            'increment': 0,
            'case': 'SKIP',
            'case_infos': [],
            'facelets': '',
        }

    def normalize_value(self, metric: str, name: str, value: float,  # noqa: PLR0911
                        default: str, *, threshold: float = 1.2) -> str:
        """
        Normalize a metric value against benchmark thresholds.

        Compares the value to configured norms and returns a status
        indicating performance level (success, caution, or warning).

        Args:
            metric: Metric category (e.g., 'tps', 'execution').
            name: Specific metric name within category.
            value: Measured value to normalize.
            default: Default status if no norm is configured.
            threshold: Multiplier for warning threshold (default 1.2).

        Returns:
            Performance status: 'success', 'caution', 'warning', or default.

        """
        norm = self.norms.get(metric, {}).get(name)
        if norm is None:
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
        """
        Calculates overall solve quality score.

        Returns:
            Numerical score representing solve quality (default 20).

        """
        return 20


def get_step_config(step_name: str, value: str, default: Any = None) -> Any:  # noqa: ANN401
    """
    Retrieve configuration value for a solving step.

    Args:
        step_name: Name of the step (e.g., 'Cross', 'OLL', 'F2L 1').
        value: Configuration key to retrieve (e.g., 'mask', 'triggers').
        default: Value to return if step or key not found.

    Returns:
        Configuration value if found, otherwise default value.

    """
    return STEPS_CONFIG.get(step_name, {}).get(value, default)
