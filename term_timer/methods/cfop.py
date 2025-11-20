"""CFOP method analysis with Cross, F2L, OLL, and PLL detection."""
from collections.abc import Callable
from functools import cached_property
from typing import ClassVar
from typing import Final

from cubing_algs.algorithm import Algorithm
from cubing_algs.masks import F2L_BL_MASK
from cubing_algs.masks import F2L_BR_MASK
from cubing_algs.masks import F2L_FL_MASK
from cubing_algs.masks import F2L_FR_MASK

from term_timer.constants import SECOND
from term_timer.methods.base import Analyser
from term_timer.methods.cases.encoders import f2l_case_encoder
from term_timer.methods.cases.encoders import oll_case_encoder
from term_timer.methods.cases.encoders import pll_case_encoder
from term_timer.methods.types import StepSummary

CFOP_CASE_ENCODERS: Final[dict[str, Callable[[str], str]]] = {
    'OLL': oll_case_encoder,
    'PLL': pll_case_encoder,

    'F2L Front Left': f2l_case_encoder(F2L_FR_MASK),
    'F2L Front Right': f2l_case_encoder(F2L_FL_MASK),
    'F2L Back Left': f2l_case_encoder(F2L_BR_MASK),
    'F2L Back Right': f2l_case_encoder(F2L_BL_MASK),
}


class CFOPAnalyser(Analyser):
    """
    Analyzes solves using the CFOP method with step detection and scoring.

    CFOP (Cross, F2L, OLL, PLL) is the most popular speedcubing method.
    This analyser tracks solve progress through each step, detects cases,
    and calculates quality scores based on move efficiency and execution.

    Attributes:
        name: Method name identifier.
        step_list: Ordered sequence of CFOP steps.
        aufs: AUF (Adjust U Face) configuration for each step.
        norms: Expected values for moves, time percentages, and execution
            quality for each step.
        aggregate: Step indices for aggregated statistics.

    """

    name = 'CFOP'
    step_list: tuple[str, ...] = ('Cross', 'F2L', 'OLL', 'PLL')
    aufs: ClassVar[dict[str, list[bool]]] = {
        'OLL': [True, False],
        'PLL': [True, True],
    }
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {
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
    aggregate: ClassVar[dict[str, int]] = {
        'oll': -2,
        'pll': -1,
    }

    def compute_progress(self, facelets: str,
                         progress: int) -> tuple[int, list[str]]:
        """
        Calculate current solve progress through CFOP steps.

        Iterates through remaining steps to determine how far the solve has
        progressed by checking which steps are complete.

        Args:
            facelets: 54-character cube state string.
            progress: Current step index in the solve sequence.

        Returns:
            Tuple containing the updated progress index and an empty list
            (case information not tracked in base CFOP).

        """
        current_progress = progress

        for name in self.step_list[progress:-1]:
            if self.check_step(name, facelets, self.orientation_faces):
                current_progress += 1
            else:
                break

        return current_progress, []

    def correct_summary(self, summary: list[StepSummary]) -> None:
        """
        Apply CFOP-specific corrections to step summary data.

        Fixes step naming issues such as OLL skips being misidentified as
        F2L, then applies standard CFOP summary corrections.

        Args:
            summary: List of step summary dictionaries to be corrected
                in-place.

        """
        # Fix OLL SKIP instead of F2L
        for info in summary:
            if info['increment'] > 1 and 'OLL' in info['name']:
                info['name'] = 'F2L'

        self.correct_summary_cfop(summary)

    @cached_property
    def score(self) -> float:  # noqa: C901
        """
        Calculates solve quality score based on efficiency and execution.

        Evaluates solve quality by rewarding XCrosses and fast lookahead
        while penalizing inefficient crosses and excessive AUFs. Base score
        is 20, with bonuses and penalties applied.

        Returns:
            Quality score ranging from ~10 (poor) to 50 (exceptional).
            Full cube solve in one step returns maximum score of 50.

        """
        bonus: float = 0

        step_one = self.summary[0]
        if 'XCross' in step_one['name']:
            bonus = 2 * step_one['name'].count('X')

        elif 'Full Cube' in step_one['name']:
            return 50

        malus = 0.0
        if 'Cross' in step_one['name']:
            cross_norm = self.norms.get('moves', {}).get(step_one['name'], 0)
            if cross_norm and isinstance(cross_norm, (int | float)):
                malus += (
                    step_one['moves_prettified'].metrics.htm
                    - cross_norm
                )

        for info in self.summary:
            if info['type'] != 'virtual' and info['moves']:
                if info['post_pause'] < SECOND * 0.5:
                    bonus += 0.5
                elif info['post_pause'] < SECOND:
                    bonus += 0.25

                if info['name'] in {'OLL', 'PLL'}:
                    for auf in info['aufs']:
                        if auf:
                            malus += int(auf)

        return 20 + bonus - malus

    def correct_summary_cfop(self, summary: list[StepSummary]) -> None:  # noqa: C901
        """
        Ensure summary contains all CFOP steps with skip placeholders.

        Inserts placeholder entries for skipped steps (PLL, OLL, F2L) and
        identifies OLL/PLL/F2L cases from cube state. Modifies summary
        in-place to maintain consistent structure.

        Args:
            summary: List of step summary dictionaries to be corrected
                in-place.

        """
        # Skipped PLL insert
        if summary[-1]['name'] != 'PLL':
            summary.append(
                {
                    'type': 'skipped',
                    'name': 'PLL',
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
                },
            )

        # Skipped F2L insert
        if 'F2L' not in summary[1]['name']:
            summary.insert(
                1,
                {
                    'type': 'skipped',
                    'name': 'F2L',
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
                },
            )

        # Guess OLL/PLL cases
        for info in summary:
            if info['name'] == 'OLL':
                facelets = info['facelets']
                if facelets:
                    info['case'] = self.get_step_case(
                        'OLL', facelets,
                        self.orientation_faces,
                        CFOP_CASE_ENCODERS['OLL'],
                    )

            elif info['name'] == 'PLL':
                facelets = info['facelets']
                if facelets:
                    info['case'] = self.get_step_case(
                        'PLL', facelets,
                        self.orientation_faces,
                        CFOP_CASE_ENCODERS['PLL'],
                    )

            elif info['name'].startswith('F2L '):
                facelets = info['facelets']
                case_infos = info['case_infos']
                if facelets and case_infos:
                    info['case'] = self.get_step_case(
                        'F2L', facelets,
                        self.orientation_faces,
                        CFOP_CASE_ENCODERS[f'F2L { case_infos[0] }'],
                    )


class CF4OPAnalyser(CFOPAnalyser):
    """
    Analyzes solves using CFOP with individual F2L pair tracking.

    CF4OP is a variant of CFOP that tracks each of the four F2L pairs
    separately, enabling detailed analysis of F2L efficiency and lookahead.
    Supports XCross detection and aggregates F2L pairs into virtual step.

    Attributes:
        name: Method name identifier.
        step_list: Ordered sequence including individual F2L pairs.
        aufs: AUF configuration for OLL and PLL steps.
        norms: Expected values for moves, time percentages, and execution
            quality for each step including individual F2L pairs.

    """

    name = 'CF4OP'
    step_list: tuple[str, ...] = (
        'Cross',
        'F2L 1', 'F2L 2', 'F2L 3', 'F2L 4',
        'OLL', 'PLL',
    )
    aufs: ClassVar[dict[str, list[bool]]] = {
        'OLL': [True, True],
        'PLL': [True, True],
    }
    norms: ClassVar[dict[str, dict[str, float | tuple[float, float]]]] = {
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

    def compute_progress(self, facelets: str,
                         progress: int) -> tuple[int, list[str]]:
        """
        Calculate progress through CF4OP steps with F2L pair tracking.

        Determines solve progress by checking cross completion, individual
        F2L pairs, and OLL completion. Returns pair identifiers for tracking
        which specific F2L slots have been solved.

        Args:
            facelets: 54-character cube state string.
            progress: Current step index in the solve sequence.

        Returns:
            Tuple containing the updated progress index and list of solved
            F2L pair identifiers (e.g., ['Front Right', 'Back Left']).

        """
        if progress == 6:
            return 6, []

        if not self.check_step('Cross', facelets, self.orientation_faces):
            return 0, []

        if not self.check_step('OLL', facelets, self.orientation_faces):
            name = ['F2L 1', 'F2L 2', 'F2L 3', 'F2L 4']
            # Anticipated compensation
            # because check_step will perform computing using opposite top face
            # but keep front face, which rotate the cube like a z2 rotation.
            pair = ['Front Left', 'Front Right', 'Back Left', 'Back Right']

            score = 1
            pairs: list[str] = []

            for n, p in zip(name, pair, strict=True):
                result = self.check_step(n, facelets, self.orientation_faces)
                if result:
                    score += 1
                    pairs.append(p)

            return score, pairs

        return 6, []

    def correct_summary(self, summary: list[StepSummary]) -> None:  # noqa: C901, PLR0912, PLR0915
        """
        Apply CF4OP-specific corrections and aggregate F2L pairs.

        Identifies XCross variations, merges multiple F2L pairs solved
        together, creates virtual F2L summary step from individual pairs,
        and applies standard CFOP corrections. Modifies summary in-place.

        Args:
            summary: List of step summary dictionaries to be corrected
                in-place.

        """
        # Merge XCrosses
        if summary[0]['name'] == 'F2L 1':
            summary[0]['name'] = 'XCross'

        elif summary[0]['name'] == 'F2L 2':
            summary[0]['name'] = 'XXCross'

        elif summary[0]['name'] == 'F2L 3':
            summary[0]['name'] = 'XXXCross'

        elif summary[0]['name'] == 'F2L 4':
            summary[0]['name'] = 'XXXXCross'

        elif len(summary) == 1:
            summary[0]['name'] = 'Full Cube'

        # Merge double F2L inserts
        case_infos = []
        for i, info in enumerate(summary):
            case_infos.extend(info['case_infos'])
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
                    info['case_infos'] = sorted(
                        {
                            'Front Left', 'Front Right',
                            'Back Left', 'Back Right',
                        } - set(case_infos),
                    )

        self.correct_summary_cfop(summary)

        # Summary for F2L
        f2l: StepSummary = {
            'type': 'virtual',
            'name': 'F2L',
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
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        }

        f2l_steps = len(
            [
                info for info in summary
                if 'F2L ' in info['name']
             ],
        )

        insert_f2l = False
        auf_0_sum = 0
        auf_1_sum = 0
        for info in summary:
            if 'F2L ' in info['name']:
                info['type'] = 'substep'

                insert_f2l = True
                f2l['moves'].extend(info['moves'])
                f2l['moves_reoriented'].extend(info['moves_reoriented'])
                f2l['moves_humanized'].extend(info['moves_humanized'])
                f2l['moves_prettified'].extend(info['moves_prettified'])
                f2l['times'].extend(info['times'])
                f2l['index'].extend(info['index'])
                f2l['qtm'] += info['qtm']
                f2l['total'] += info['total']
                f2l['execution'] += info['execution']
                f2l['recognition'] += info['recognition']
                f2l['post_pause'] = info['post_pause']
                if info['aufs'][0] is not None:
                    auf_0_sum += info['aufs'][0]
                if info['aufs'][1] is not None:
                    auf_1_sum += info['aufs'][1]
                f2l['total_percent'] += info['total_percent']
                f2l['execution_percent'] += info['execution_percent']
                f2l['recognition_percent'] += info['recognition_percent']
                f2l['step_execution_percent'] += info['step_execution_percent']
                f2l['step_recognition_percent'] += info['step_recognition_percent']  # noqa: E501

        if f2l_steps:
            f2l['step_execution_percent'] /= f2l_steps
            f2l['step_recognition_percent'] /= f2l_steps

        if auf_0_sum:
            f2l['aufs'][0] = auf_0_sum
        if auf_1_sum:
            f2l['aufs'][1] = auf_1_sum

        if insert_f2l:
            if 'F2L' not in summary[0]['name']:
                summary.insert(1, f2l)
            else:
                summary.insert(0, f2l)
