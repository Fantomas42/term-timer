"""CFOP method analysis with Cross, F2L, OLL, and PLL detection."""
from collections.abc import Callable
from functools import cached_property
from typing import ClassVar
from typing import Final

from cubing_algs.annotations import CubeFacelets
from cubing_algs.masks import F2L_BL_MASK
from cubing_algs.masks import F2L_BR_MASK
from cubing_algs.masks import F2L_FL_MASK
from cubing_algs.masks import F2L_FR_MASK

from term_timer.constants import SECOND
from term_timer.methods.annotations import AufCounts
from term_timer.methods.annotations import AufFlags
from term_timer.methods.annotations import EncodedMask
from term_timer.methods.annotations import MethodNorms
from term_timer.methods.annotations import NormRange
from term_timer.methods.annotations import StepSummary
from term_timer.methods.annotations import TrackedStep
from term_timer.methods.base import Analyser
from term_timer.methods.masks.encoders import f2l_case_encoder
from term_timer.methods.masks.encoders import oll_case_encoder
from term_timer.methods.masks.encoders import pll_case_encoder

CFOP_CASE_ENCODERS: Final[dict[str, Callable[[CubeFacelets], EncodedMask]]] = {
    'OLL': oll_case_encoder,
    'PLL': pll_case_encoder,

    'F2L Front Right': f2l_case_encoder(F2L_FR_MASK),
    'F2L Front Left': f2l_case_encoder(F2L_FL_MASK),
    'F2L Back Right': f2l_case_encoder(F2L_BR_MASK),
    'F2L Back Left': f2l_case_encoder(F2L_BL_MASK),
}

F2L_SLOTS = [
    'Front Right',
    'Front Left',
    'Back Right',
    'Back Left',
]


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
    aufs: ClassVar[dict[str, AufFlags]] = {
        'OLL': AufFlags(pre=True, post=False),
        'PLL': AufFlags(pre=True, post=True),
    }
    norms: ClassVar[MethodNorms] = {
        'moves': {
            'Cross': 6,
            # Mean of shortest algs for each cases + aufs
            'F2L': (7.2 + 1) * 4,
            'OLL': 9.37 + 2,
            'PLL': 11.48 + 2,
        },
        'percent': {
            'Cross': 12.0,
            'F2L': 50.0,
            'OLL': 16.5,
            'PLL': 21.5,
        },
        'recognition': {
            'Cross': NormRange(0.0, 0.0),
            'F2L': NormRange(30.0, 40.0),
            'OLL': NormRange(10.0, 20.0),
            'PLL': NormRange(5.0, 10.0),
        },
        'execution': {
            'Cross': NormRange(100.0, 100.0),
            'F2L': NormRange(60.0, 70.0),
            'OLL': NormRange(80.0, 90.0),
            'PLL': NormRange(90.0, 95.0),
        },
        'solve': {
            'recognition': NormRange(0, 20),
            'execution': NormRange(80, 100),
        },
    }
    aggregate: ClassVar[dict[str, str]] = {
        'oll': 'OLL',
        'pll': 'PLL',
    }

    def compute_progress(
            self,
            facelets: CubeFacelets,
            progress: int,
    ) -> tuple[int, list[str]]:
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
            if self.check_step(name, facelets):
                current_progress += 1
            else:
                break

        return current_progress, []

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

        step_done = len(
            [
                step
                for step in self.summary
                if 'step' in step['type']
            ],
        )

        if step_done == 1:
            bonus += 20

        step_one = self.summary[0]
        if 'XCross' in step_one['name']:
            bonus += 2 * step_one['name'].count('X')

        malus = 0.0
        if 'Cross' in step_one['name'] and step_one['type'] != 'skipped':
            cross_norm = self.norms['moves'].get(step_one['name'], 0)
            if cross_norm:
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

                if info['name'] in {'OLL', 'PLL'} and info['case'] != 'SKIP':
                    for auf in info['aufs']:
                        if auf:
                            malus += int(auf)

        return 20 + bonus - malus

    def correct_summary(self, summary: list[StepSummary]) -> None:
        """
        Apply CFOP-specific corrections to step summary data.

        Fixes missing step, then applies standard CFOP summary corrections.

        Args:
            summary: List of step summary dictionaries to be corrected
                in-place.

        """
        for info in summary:
            if info['increment'] > 1:
                step_idx = self.step_list.index(info['name'])
                first_step = self.step_list[step_idx - info['increment'] + 1]
                info['name'] = first_step

        names = [s['name'] for s in summary]
        for step_position, step_name in enumerate(self.step_list):
            if step_name not in names:
                summary.insert(
                    step_position,
                    self.create_skipped_summary(step_name),
                )

        self.set_cases_cfop(summary)

    def set_cases_cfop(self, summary: list[StepSummary]) -> None:
        """
        Identify OLL/PLL/F2L cases from cube state.

        Modifies summary in-place to maintain consistent structure.

        Args:
            summary: List of step summary dictionaries to be updated
                in-place.

        """
        for info in summary:
            if info['name'] == 'OLL':
                facelets = info['facelets']
                if facelets:
                    info['case'] = self.get_step_case(
                        'OLL', facelets,
                        CFOP_CASE_ENCODERS['OLL'],
                    )

            elif info['name'] == 'PLL':
                facelets = info['facelets']
                if facelets:
                    info['case'] = self.get_step_case(
                        'PLL', facelets,
                        CFOP_CASE_ENCODERS['PLL'],
                    )

            elif info['name'].startswith('F2L '):
                facelets = info['facelets']
                case_infos = info['case_infos']
                if facelets and case_infos:
                    info['case'] = self.get_step_case(
                        'F2L', facelets,
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
    step_groups: tuple[tuple[TrackedStep, ...], ...] = (
        (TrackedStep('Cross', None),),
        (
            TrackedStep('F2L 1', 'F2L FR'),
            TrackedStep('F2L 2', 'F2L FL'),
            TrackedStep('F2L 3', 'F2L BR'),
            TrackedStep('F2L 4', 'F2L BL'),
        ),
        (TrackedStep('OLL', None),),
        (TrackedStep('PLL', None),),
    )
    aufs: ClassVar[dict[str, AufFlags]] = {
        'OLL': AufFlags(pre=True, post=True),
        'PLL': AufFlags(pre=True, post=True),
    }
    norms: ClassVar[MethodNorms] = {
        'moves': {
            'Cross': 6,
            'XCross': 8,
            'XXCross': 10,
            'XXXCross': 12,
            'XXXXCross': 14,
            # Mean of shortest algs for each cases + aufs
            'F2L': (7.2 + 1) * 4,
            'F2L 1': 7.2 + 1,
            'F2L 2': 7.2 + 1,
            'F2L 3': 7.2 + 1,
            'F2L 4': 7.2 + 1,
            'OLL': 9.37 + 2,
            'PLL': 11.48 + 2,
        },
        'percent': {
            'Cross': 12.0,
            'XCross': 20.0,
            'XXCross': 30.0,
            'XXXCross': 40.0,
            'XXXXCross': 50.0,
            'F2L': 50.0,
            'F2L 1': 12.5,
            'F2L 2': 12.5,
            'F2L 3': 12.5,
            'F2L 4': 12.5,
            'OLL': 16.5,
            'PLL': 21.5,
        },
        'recognition': {
            'Cross': NormRange(0.0, 0.0),
            'F2L': NormRange(30.0, 40.0),
            'F2L 1': NormRange(30.0, 40.0),
            'F2L 2': NormRange(30.0, 40.0),
            'F2L 3': NormRange(30.0, 40.0),
            'F2L 4': NormRange(30.0, 40.0),
            'OLL': NormRange(10.0, 20.0),
            'PLL': NormRange(5.0, 10.0),
        },
        'execution': {
            'Cross': NormRange(100.0, 100.0),
            'F2L': NormRange(60.0, 70.0),
            'F2L 1': NormRange(60.0, 70.0),
            'F2L 2': NormRange(60.0, 70.0),
            'F2L 3': NormRange(60.0, 70.0),
            'F2L 4': NormRange(60.0, 70.0),
            'OLL': NormRange(80.0, 90.0),
            'PLL': NormRange(90.0, 95.0),
        },
        'solve': {
            'recognition': NormRange(0, 40),
            'execution': NormRange(60, 100),
        },
    }

    def compute_progress(
            self,
            facelets: CubeFacelets,
            progress: int,
    ) -> tuple[int, list[str]]:
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

        if not self.check_step('Cross', facelets):
            return 0, []

        if not self.check_step('OLL', facelets):
            name = ['F2L 1', 'F2L 2', 'F2L 3', 'F2L 4']

            score = 1
            pairs: list[str] = []

            for n, p in zip(name, F2L_SLOTS, strict=True):
                result = self.check_step(n, facelets)
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
        first = summary[0]
        # Merge XCrosses
        if first['name'] == 'F2L 1':
            first['name'] = 'XCross'

        elif first['name'] == 'F2L 2':
            first['name'] = 'XXCross'

        elif first['name'] == 'F2L 3':
            first['name'] = 'XXXCross'

        elif first['name'] in {'F2L 4', 'OLL'}:
            first['name'] = 'XXXXCross'

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
                        set(F2L_SLOTS) - set(case_infos),
                    )

        # Merge remaining F2L pairs into the last F2L entry
        f2l_covered: set[int] = set()
        last_f2l_idx = -1

        for i, info in enumerate(summary):
            if 'Cross' in info['name']:
                f2l_covered.update(range(1, info['name'].count('X') + 1))
            elif 'F2L ' in info['name']:
                last_f2l_idx = i
                for part in info['name'].replace('F2L ', '').split('+'):
                    if part.isdigit():
                        f2l_covered.add(int(part))

        if last_f2l_idx >= 0 and len(f2l_covered) < 4:
            last = summary[last_f2l_idx]
            missing = sorted({1, 2, 3, 4} - f2l_covered)
            if missing:
                current = [
                    int(p)
                    for p in last['name'].replace('F2L ', '').split('+')
                    if p.isdigit()
                ]
                all_nums = sorted(current + missing)
                last['name'] = 'F2L ' + '+'.join(map(str, all_nums))
                last['case_infos'] = sorted(
                    set(F2L_SLOTS) - set(case_infos),
                )

        self.set_cases_cfop(summary)

        if 'Cross' not in summary[0]['name']:
            summary.insert(0, self.create_skipped_summary('Cross'))

        # Summary for F2L
        f2l: StepSummary = self.create_skipped_summary('F2L')
        f2l_steps = len(
            [
                info for info in summary
                if 'F2L ' in info['name']
             ],
        )

        auf_0_sum = 0
        auf_1_sum = 0
        for info in summary:
            if 'F2L ' in info['name']:
                info['type'] = 'substep'

                f2l['type'] = 'virtual'
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

        f2l['aufs'] = AufCounts(auf_0_sum or None, auf_1_sum or None)

        summary.insert(1, f2l)

        all_steps = [s['name'] for s in summary]

        if 'PLL' not in all_steps:
            summary.append(self.create_skipped_summary('PLL'))

        if 'OLL' not in all_steps:
            summary.insert(-1, self.create_skipped_summary('OLL'))
