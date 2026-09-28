"""Algorithm detail view."""
from operator import itemgetter
from typing import TYPE_CHECKING

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.cases import get_case
from cubing_algs.constants import CORNER_NAMES
from cubing_algs.constants import EDGE_NAMES
from cubing_algs.constants import ORIENTATION_FACE_MOVES
from cubing_algs.ergonomics import DEFAULT_MOVE_PROPERTIES
from cubing_algs.ergonomics import MOVE_DATA
from cubing_algs.ergonomics import PAUSE_TIME
from cubing_algs.ergonomics import TRANSITION_PENALTIES
from cubing_algs.ergonomics import HandDominance
from cubing_algs.ergonomics import compute_move_execution_time
from cubing_algs.ergonomics import get_move_key
from cubing_algs.ergonomics import get_transition_penalty
from cubing_algs.impacts import ImpactData
from cubing_algs.masks import compute_algorithm_mask
from cubing_algs.parsing import parse_moves
from cubing_algs.structure import Structure
from cubing_algs.transform.invert import invert_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves
from cubing_algs.transform.symmetry import symmetry_c_moves
from cubing_algs.transform.symmetry import symmetry_m_moves
from cubing_algs.transform.symmetry import symmetry_s_moves
from cubing_algs.vcube import VCube

if TYPE_CHECKING:
    from cubing_algs.move import Move

from term_timer.config import CUBE_ORIENTATION
from term_timer.in_out import read_trainings
from term_timer.methods.base import FaceletAnalyser
from term_timer.methods.masks.encoders import oll_case_encoder
from term_timer.methods.masks.encoders import pll_case_encoder
from term_timer.orientation import get_orientation_moves
from term_timer.server.annotations import AlgorithmCase
from term_timer.server.annotations import AlgorithmChart
from term_timer.server.annotations import AlgorithmCharts
from term_timer.server.annotations import AlgorithmDetailContext
from term_timer.server.annotations import AlgorithmMoveStep
from term_timer.server.annotations import AlgorithmPatternGroup
from term_timer.server.annotations import AlgorithmStructureRow
from term_timer.server.annotations import AlgorithmVariation
from term_timer.server.annotations import AlgorithmVariationRow
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import CubieCycle
from term_timer.server.annotations import PlayerData
from term_timer.server.filters import algorithm_tokens
from term_timer.server.views.academy import AcademyView
from term_timer.server.views.base import View

# The hand of a move, as the move track names it.
HAND_NAMES = {
    HandDominance.RIGHT: 'right',
    HandDominance.LEFT: 'left',
    HandDominance.AMBIDEXTROUS: 'both',
}

TRANSITION_NAMES = {
    penalty: name for name, penalty in TRANSITION_PENALTIES.items()
}

# Weight of the least comfortable move: its discomfort is 1.
LEAST_MOVE_WEIGHT = 0.5

PATTERN_CATEGORIES = {
    'state': 'State',
    'orientation': 'Orientation',
    'permutation': 'Permutation',
    'first_layer': 'First layer',
    'last_layer': 'Last layer',
    'scramble': 'Scramble',
    'cycle': 'Cycles',
}

# Score bands, from the best: the tone of a score at least
# as high as the bound.
ERGONOMICS_TONES = ((0.65, 'good'), (0.5, ''), (0.35, 'warn'))
MEMORY_TONES = ((0.6, 'good'), (0.4, ''), (0.2, 'warn'))

# Cycle order the analysis reports for an algorithm it gave up on.
CYCLES_UNBOUNDED = 100
CYCLES_SHORT = 10

# Edges of a face are its odd stickers; their arrows are drawn red,
# those of the corners black, as the case database does.
FACE_STICKERS = 9

# The AUFs tried after an algorithm to draw its arrows, in order.
LAST_LAYER_AUFS = ('', 'U', "U'", 'U2')


class AlgorithmDetailView(View):
    """View for displaying algorithm with transformations and variations."""

    template_name = 'algorithm.html'

    def __init__(self, algorithm: str, orientation: CubeOrientation) -> None:
        """
        Initialize algorithm detail view.

        Args:
            algorithm: Algorithm string in standard cube notation.
            orientation: Cube orientation for display.

        """
        self.algorithm = Algorithm.parse_moves(algorithm)
        self.orientation = orientation
        self.cube_size = max(3, self.algorithm.min_cube_size)

    @staticmethod
    def score_tone(score: float, bands: tuple[tuple[float, str], ...]) -> str:
        """
        Tone of a score between 0 and 1 by its band.

        Returns:
            The tone of the first band the score reaches, bad under all.

        """
        for bound, tone in bands:
            if score >= bound:
                return tone
        return 'bad'

    @staticmethod
    def cycles_tone(cycles: int) -> str:
        """
        Tone of a cycle order: short is good, unbounded is bad.

        Returns:
            The tone of the cycle order.

        """
        if cycles >= CYCLES_UNBOUNDED:
            return 'bad'
        if cycles <= CYCLES_SHORT:
            return 'good'
        return 'warn'

    @staticmethod
    def solved_case_code(
            algorithm: Algorithm, impacts: ImpactData,
    ) -> tuple[str, str] | None:
        """
        Find the CFOP last layer case an algorithm solves.

        The algorithm must keep the first two layers; its inverse,
        applied on a solved cube, is then the case it solves. The PLL
        is only looked for once the last layer is oriented: its encoder
        needs the four colours of the sides.

        Returns:
            The step (OLL or PLL) and the case code, None when the
            algorithm touches the first two layers or leaves the last
            layer as it is.

        """
        patterns = impacts.cubies_patterns
        if patterns is None or 'F2L_COMPLETE' not in patterns.first_layer:
            return None

        cube = VCube()
        cube.rotate(algorithm.transform(invert_moves))
        facelets = cube.state

        oll = FaceletAnalyser.get_step_case('OLL', facelets, oll_case_encoder)
        if oll and oll != 'SKIP':
            return 'OLL', oll
        if oll == 'SKIP':
            pll = FaceletAnalyser.get_step_case(
                'PLL', facelets, pll_case_encoder,
            )
            if pll and pll != 'SKIP':
                return 'PLL', pll
        return None

    @staticmethod
    def last_layer_arrows(algorithm: Algorithm) -> str:
        """
        Arrows of the stickers an algorithm moves around the U face.

        An algorithm often ends one AUF away from solved: the AUF added
        is the one moving the fewest stickers, as the case database
        draws its arrows, the first of LAST_LAYER_AUFS on a tie.

        Returns:
            The arrows in the syntax of the case database, edges red and
            corners black.

        """
        best: list[str] | None = None
        for auf in LAST_LAYER_AUFS:
            permutations = (algorithm + auf).impacts().facelets_permutations
            arrows = [
                f'U{ origin }U{ target }-'
                f'{ "red" if origin % 2 else "black" }'
                for origin, target in sorted(permutations.items())
                if origin < FACE_STICKERS and target < FACE_STICKERS
            ]
            if best is None or len(arrows) < len(best):
                best = arrows
        return ','.join(best or [])

    def build_solved_case(self, impacts: ImpactData) -> AlgorithmCase | None:
        """
        Describe the last layer case the algorithm solves.

        Returns:
            The case, with its academy page and whether the algorithm is
            the one saved while training or the main one of the case.

        """
        found = (
            self.solved_case_code(self.algorithm, impacts)
            if self.cube_size == 3 else None
        )
        if found is None:
            return None

        step, code = found
        case = get_case(f'CFOP/{ step }', code)
        trainings = read_trainings('CFOP', step)
        case_training = trainings.cases.get(code) if trainings else None
        solution = case_training.solution if case_training else ''
        text = str(self.algorithm)

        return {
            'step': step,
            'code': code,
            'label': f'{ step } { code }',
            'aliases': case.aliases,
            'href': AcademyView.case_url('CFOP', step, code),
            'mode': step.lower(),
            'arrows': (
                self.last_layer_arrows(self.algorithm) if step == 'PLL'
                else ''
            ),
            'yours': bool(solution) and str(
                parse_moves(solution, trust_input=True),
            ) == text,
            'main': str(case.main_algorithm) == text,
        }

    @staticmethod
    def structure_parts(
            structures: list[Structure], length: int,
    ) -> tuple[list[str], list[int]]:
        """
        Name the member of its structure each move belongs to.

        A conjugate [A: B] reads A B A', a commutator [A, B] reads
        A B A' B'. A structure whose moves cancel does not split that
        way and is only marked; one overlapping an earlier structure is
        skipped.

        Returns:
            The member of each move, empty outside any structure, and
            the number of its structure, 0 outside any.

        """
        parts = [''] * length
        owners = [0] * length
        for number, structure in enumerate(structures, 1):
            span = range(structure.start, min(structure.end, length))
            if any(owners[index] for index in span):
                continue
            setup = len(structure.setup)
            action = len(structure.action)
            layout = ['A'] * setup + ['B'] * action + ["A'"] * setup
            if structure.type == 'commutator':
                layout += ["B'"] * action
            if len(layout) != len(span):
                layout = ['·'] * len(span)
            for index, part in zip(span, layout, strict=True):
                parts[index] = part
                owners[index] = number
        return parts, owners

    def build_track(
            self, structures: list[Structure],
    ) -> list[AlgorithmMoveStep]:
        """
        Follow the hands move by move.

        A regrip is counted as the ergonomics analysis does: on every
        rotation, and on a transition at least as hard as turning the
        opposite face, a rotation resetting the hands.

        Returns:
            One step per move, pauses included.

        """
        parts, owners = self.structure_parts(structures, len(self.algorithm))
        opposite = TRANSITION_PENALTIES['opposite']
        track: list[AlgorithmMoveStep] = []
        previous: Move | None = None

        for index, move in enumerate(self.algorithm):
            properties = MOVE_DATA.get(
                get_move_key(move), DEFAULT_MOVE_PROPERTIES,
            )
            step: AlgorithmMoveStep = {
                'move': str(move),
                'hand': HAND_NAMES[properties.hand],
                'finger': properties.finger.value,
                'time': compute_move_execution_time(move),
                'load': min(1.0, max(
                    0.0, (1 - properties.weight) / (1 - LEAST_MOVE_WEIGHT),
                )),
                'transition': '',
                'regrip': False,
                'part': parts[index],
                'structure': owners[index],
            }
            if move.is_pause:
                step.update({
                    'hand': 'pause', 'finger': '', 'time': PAUSE_TIME,
                    'load': 0.0,
                })
            elif move.is_rotation_move:
                step.update({
                    'hand': 'rotation', 'finger': '', 'transition': 'rotation',
                    'regrip': True,
                })
                previous = None
            else:
                if previous is not None:
                    penalty = get_transition_penalty(previous, move)
                    step['transition'] = TRANSITION_NAMES.get(penalty, '')
                    step['regrip'] = penalty >= opposite
                previous = move
            track.append(step)

        return track

    @staticmethod
    def build_structures(
            structures: list[Structure],
    ) -> list[AlgorithmStructureRow]:
        """
        List the structures detected, numbered as the move track marks.

        Returns:
            One row per structure, its moves counted from 1.

        """
        return [
            {
                'number': number,
                'kind': structure.type,
                'classification': structure.classification,
                'notation': str(structure),
                'setup': str(structure.setup),
                'action': str(structure.action),
                'first': structure.start + 1,
                'last': structure.end,
                'moves': structure.move_count,
                'pure': structure.is_pure,
                'cancels': structure.has_cancellations,
                'score': structure.score,
            }
            for number, structure in enumerate(structures, 1)
        ]

    @staticmethod
    def build_cubies(impacts: ImpactData) -> tuple[list[CubieCycle], list[str]]:
        """
        Name the pieces the algorithm cycles, and those it only turns.

        Returns:
            The cycles of corners then edges, and the pieces twisted or
            flipped in place. Empty beyond the 3x3x3.

        """
        cycles: list[CubieCycle] = []
        twisted: list[str] = []

        for kind, names, found, permutation, orientation in (
                ('corner', CORNER_NAMES, impacts.cubies_corner_cycles,
                 impacts.cubies_corner_permutation,
                 impacts.cubies_corner_orientation),
                ('edge', EDGE_NAMES, impacts.cubies_edge_cycles,
                 impacts.cubies_edge_permutation,
                 impacts.cubies_edge_orientation),
        ):
            cycles.extend(
                {'kind': kind, 'pieces': [names[index] for index in cycle]}
                for cycle in found or []
            )
            twisted.extend(
                names[index]
                for index, (piece, turned) in enumerate(zip(
                    permutation or [], orientation or [], strict=False,
                ))
                if piece == index and turned
            )

        return cycles, twisted

    @staticmethod
    def build_patterns(impacts: ImpactData) -> list[AlgorithmPatternGroup]:
        """
        Group the patterns the algorithm leaves on a solved cube.

        Returns:
            One group per category holding a pattern.

        """
        patterns = impacts.cubies_patterns
        if patterns is None:
            return []

        return [
            {
                'label': label,
                'patterns': [
                    pattern.replace('_', ' ')
                    for pattern in getattr(patterns, category)
                ],
            }
            for category, label in PATTERN_CATEGORIES.items()
            if getattr(patterns, category)
        ]

    def case_label(self, algorithm: Algorithm) -> str:
        """
        Name the last layer case a variation solves.

        Returns:
            The step and code of the case, empty when there is none.

        """
        if self.cube_size != 3:
            return ''
        found = self.solved_case_code(algorithm, algorithm.impacts())
        return ' '.join(found) if found else ''

    def build_variations(
            self, variations: list[AlgorithmVariation],
    ) -> list[AlgorithmVariationRow]:
        """
        Compare the variations with the original, the original first.

        Returns:
            One row per algorithm, the most comfortable marked best.

        """
        original = self.algorithm
        htm = original.metrics.htm
        ergonomics = original.ergonomics.ergonomic_score * 100
        memory = original.memory.memory_score * 100

        compared: list[AlgorithmVariation] = [
            {'label': 'Original', 'algorithm': original},
            *variations,
        ]
        rows: list[AlgorithmVariationRow] = []
        for variation in compared:
            algorithm = variation['algorithm']
            score = algorithm.ergonomics.ergonomic_score * 100
            recall = algorithm.memory.memory_score * 100
            rows.append({
                'label': variation['label'],
                'text': str(algorithm),
                'tokens': algorithm_tokens(algorithm),
                'htm': algorithm.metrics.htm,
                'htm_delta': algorithm.metrics.htm - htm,
                'ergonomics': score,
                'ergonomics_delta': score - ergonomics,
                'memory': recall,
                'memory_delta': recall - memory,
                'case': self.case_label(algorithm),
                'href': f'/algorithm/{ algorithm }/',
                'original': algorithm is original,
                'best': False,
            })

        best = max(rows, key=itemgetter('ergonomics'))
        best['best'] = True

        return rows

    def build_charts(self, impacts: ImpactData) -> AlgorithmCharts:
        """
        Gather the data of the charts, one per facet of the analysis.

        Returns:
            The data of every chart of the page.

        """
        metrics = self.algorithm.metrics
        ergonomics = self.algorithm.ergonomics
        memory = self.algorithm.memory

        def chart(
                pairs: list[tuple[str, float]], roles: list[str],
                maximum: float | None = None,
        ) -> AlgorithmChart:
            data: AlgorithmChart = {
                'labels': [label for label, _value in pairs],
                'values': [round(value, 2) for _label, value in pairs],
                'roles': roles,
            }
            if maximum is not None:
                data['max'] = maximum
            return data

        fingers = [
            ('Thumb', ergonomics.thumb_moves),
            ('Index', ergonomics.index_finger_moves),
            ('Middle', ergonomics.middle_finger_moves),
            ('Ring', ergonomics.ring_finger_moves),
            ('Pinky', ergonomics.pinky_finger_moves),
            ('Mixed', ergonomics.mixed_finger_moves),
        ]
        speed = min(100.0, ergonomics.estimated_tps / 6 * 100)

        return {
            'metrics': chart([
                ('HTM', metrics.htm), ('QTM', metrics.qtm),
                ('STM', metrics.stm), ('ETM', metrics.etm),
                ('RTM', metrics.rtm), ('QSTM', metrics.qstm),
            ], ['chart-1']),
            'move_types': chart([
                ('Outer', metrics.outer_moves),
                ('Inner', metrics.inner_moves),
                ('Rotations', metrics.rotations),
            ], ['chart-1', 'chart-3', 'chart-4']),
            'ergonomics': chart([
                ('Comfort', ergonomics.ergonomic_score * 100),
                ('Speed', speed),
                ('Balance', ergonomics.hand_balance_ratio * 100),
                ('Fingertricks', ergonomics.fingertrick_comfort * 100),
                ('Flow', ergonomics.flow_score * 100),
                ('Regrips', max(0, 100 - ergonomics.regrip_count * 10)),
            ], ['chart-1'], 100),
            'hands': chart([
                ('Right', ergonomics.right_hand_moves),
                ('Left', ergonomics.left_hand_moves),
                ('Both', ergonomics.both_hand_moves),
            ], ['chart-1', 'chart-3', 'chart-4']),
            'fingers': chart(
                [(label, count) for label, count in fingers
                 if count or label in {'Thumb', 'Index', 'Middle', 'Ring'}],
                ['chart-1', 'chart-3', 'chart-4', 'chart-5', 'chart-6',
                 'chart-2'],
            ),
            'memory': chart([
                ('Length', memory.length_score * 100),
                ('Chunking', memory.chunk_score * 100),
                ('Structure', memory.structure_score * 100),
                ('Repetition', memory.repetition_score * 100),
                ('Faces', memory.face_familiarity_score * 100),
                ('Flow', memory.flow_score * 100),
                ('Familiarity', memory.move_familiarity_score * 100),
            ], ['chart-3'], 100),
            'faces': chart(
                list(impacts.facelets_face_mobility.items()),
                ['chart-3'], self.cube_size ** 2,
            ),
            'pieces': chart(
                [(f'{ piece.title() }s', count) for piece, count
                 in impacts.facelets_piece_type_impact.items()],
                ['chart-1', 'chart-3', 'chart-4', 'chart-5', 'chart-6'],
            ),
        }

    def effect_mask(self, orientation_moves: Algorithm) -> str:
        """
        Mask of the facelets the algorithm moves, as /cube/ draws it.

        The image turns the cube in its orientation then applies the
        inverse of the algorithm; its mask is read in the coordinates of
        the solved cube, not in those shown, hence computed on these
        very moves.

        Returns:
            The mask, moved facelets 1, the others 2 to grey them out.

        """
        mask, _state = compute_algorithm_mask(
            orientation_moves + self.algorithm.transform(invert_moves),
            self.cube_size,
        )
        return mask.replace('0', '2')

    @staticmethod
    def breadcrumb(solved_case: AlgorithmCase | None) -> list[
            BreadcrumbItem]:
        """
        Place the algorithm under the case it solves, when it solves one.

        Returns:
            The breadcrumb, empty for any other algorithm.

        """
        if solved_case is None:
            return []
        step = solved_case['step']
        return [
            {'label': 'Academy', 'href': '/academy/'},
            {
                'label': f'CFOP { step }',
                'href': AcademyView.step_url('CFOP', step),
            },
            {'label': solved_case['code'], 'href': solved_case['href']},
            {'label': 'Algorithm', 'href': ''},
        ]

    def get_context(self) -> AlgorithmDetailContext:
        """
        Build context with algorithm variations and transformations.

        Returns:
            Dictionary containing the algorithm, its variations compared
            (inverse, Y-axis rotations, symmetries) and its analysis.

        """
        # Generate Y-axis variations
        y_variations: list[AlgorithmVariation] = [
            {
                'label': 'Y',
                'algorithm': offset_y_moves(self.algorithm),
            },
            {
                'label': 'Y2',
                'algorithm': offset_y2_moves(self.algorithm),
            },
            {
                'label': "Y'",
                'algorithm': offset_yprime_moves(self.algorithm),
            },
        ]

        symmetry_variations: list[AlgorithmVariation] = [
            {
                'label': 'Symmetry M',
                'algorithm': symmetry_m_moves(self.algorithm),
            },
            {
                'label': 'Symmetry S',
                'algorithm': symmetry_s_moves(self.algorithm),
            },
            {
                'label': 'Symmetry C',
                'algorithm': symmetry_c_moves(self.algorithm),
            },
        ]

        inverse_variation = invert_moves(self.algorithm)
        selected_orientation = self.orientation or CUBE_ORIENTATION
        orientation_moves = get_orientation_moves(selected_orientation)

        impacts = self.algorithm.impacts(self.cube_size)
        structure = self.algorithm.structure
        solved_case = self.build_solved_case(impacts)
        cubie_cycles, twisted = self.build_cubies(impacts)
        ergonomics = self.algorithm.ergonomics
        memory = self.algorithm.memory
        cycles = self.algorithm.cycles
        player: PlayerData = {
            'alg': str(self.algorithm),
            'setup': str(orientation_moves),
            'anchor': 'end',
            'puzzle': f'{ self.cube_size }x{ self.cube_size }x'
                      f'{ self.cube_size }',
            'timing': [],
            'index': {},
        }

        return {
            'algorithm': self.algorithm,
            'orientation_faces': selected_orientation,
            'available_orientations': ORIENTATION_FACE_MOVES,
            'text': str(self.algorithm),
            'tokens': algorithm_tokens(self.algorithm),
            'cube_size': self.cube_size,
            'solved_case': solved_case,
            'breadcrumb': self.breadcrumb(solved_case),
            'metrics': self.algorithm.metrics,
            'ergonomics': ergonomics,
            'memory': memory,
            'structure': structure,
            'impacts': impacts,
            'effect_mask': self.effect_mask(orientation_moves),
            'cycles': cycles,
            'tones': {
                'ergonomics': self.score_tone(
                    ergonomics.ergonomic_score, ERGONOMICS_TONES,
                ),
                'memory': self.score_tone(memory.memory_score, MEMORY_TONES),
                'cycles': self.cycles_tone(cycles),
            },
            'track': self.build_track(structure.structures),
            'structures': self.build_structures(structure.structures),
            'cubie_cycles': cubie_cycles,
            'twisted': twisted,
            'patterns': self.build_patterns(impacts),
            'variations': self.build_variations([
                {'label': 'Inverse', 'algorithm': inverse_variation},
                *y_variations,
                *symmetry_variations,
            ]),
            'charts': self.build_charts(impacts),
            'player': player,
        }
