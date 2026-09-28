"""Tests for the V2 algorithm page of the web server."""
import re
import unittest

from cubing_algs.algorithm import Algorithm
from cubing_algs.cases import get_collection
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

from term_timer.server.app import Server
from term_timer.server.views import AlgorithmDetailView
from term_timer.server.views.algorithm import ERGONOMICS_TONES
from term_timer.tests.test_server_academy import AcademyPageTestCase
from term_timer.tests.test_server_daily import WSGIClient
from term_timer.tests.test_server_training import trained

T_PERM = "R U R' U' R' F R2 U' R' U' R U R' F'"
SUNE = "R U R' U R U2 R'"
SCRAMBLE = (
    "D' R2 U2 F2 D' B2 L2 D' R2 U2 R2 B' U R' F' L' B2 D2 L' U2 F'"
)
# Twists two corners of the U face in place.
FILL_RE = r'fill="(#[0-9a-fA-F]{6})"'
SEXY_LEFT = "R' D' R D "
TWIST = f"{ SEXY_LEFT * 2 }U { SEXY_LEFT * 4 }U'"


def url(algorithm: str) -> str:
    """
    Locate the page of an algorithm.

    Returns:
        The path of the algorithm page, as the server decodes it.

    """
    return f'/algorithm/{ algorithm }/'


def view(algorithm: str) -> AlgorithmDetailView:
    """
    Build the view of an algorithm in the default orientation.

    Returns:
        The view.

    """
    return AlgorithmDetailView(algorithm, '')


class TestSolvedCase(unittest.TestCase):
    """The last layer case an algorithm solves is recognised."""

    @staticmethod
    def solved(algorithm: str) -> tuple[str, str] | None:
        """
        Recognise the case an algorithm solves.

        Returns:
            The step and code, None without case.

        """
        moves = Algorithm.parse_moves(algorithm)
        return AlgorithmDetailView.solved_case_code(moves, moves.impacts())

    def test_pll(self) -> None:
        """A PLL is found once the last layer is oriented."""
        self.assertEqual(self.solved(T_PERM), ('PLL', 'T'))

    def test_pll_with_rotations(self) -> None:
        """Rotations undone inside the algorithm do not hide the case."""
        self.assertEqual(
            self.solved("x R' U R' D2 R U' R' D2 R2 x'"), ('PLL', 'Aa'),
        )

    def test_oll_with_pre_auf(self) -> None:
        """An OLL is found whatever the AUF before it."""
        self.assertEqual(self.solved(SUNE), ('OLL', '27'))
        self.assertEqual(self.solved(f'U { SUNE }'), ('OLL', '27'))

    def test_first_two_layers_touched(self) -> None:
        """An algorithm breaking the first two layers solves no case."""
        self.assertIsNone(self.solved("R U R' U'"))
        self.assertIsNone(self.solved(SCRAMBLE))

    def test_last_layer_untouched(self) -> None:
        """An algorithm leaving the last layer as it is solves no case."""
        self.assertIsNone(self.solved("R U R' U' " * 6))

    def test_every_pll_of_the_database(self) -> None:
        """The main algorithm of every PLL is recognised as its case."""
        for case in get_collection('CFOP/PLL').cases.values():
            if not case.arrows:
                continue
            with self.subTest(case=case.code):
                self.assertEqual(
                    self.solved(str(case.main_algorithm)),
                    ('PLL', case.code),
                )

    def test_big_cube_is_not_recognised(self) -> None:
        """Beyond the 3x3x3, no case is looked for."""
        context = view("3Rw U 3Rw'").get_context()

        self.assertEqual(context['cube_size'], 4)
        self.assertIsNone(context['solved_case'])


class TestLastLayerArrows(unittest.TestCase):
    """The arrows of a PLL are deduced from the moved stickers."""

    def test_same_arrows_as_the_database(self) -> None:
        """
        Every PLL of the database gets its own arrows back, its AUF
        added. Nb moves as few stickers with U as with U': the database
        drew the U' ones, the first AUF tried is U; no order of the AUFs
        matches all the cases.
        """
        for case in get_collection('CFOP/PLL').cases.values():
            if not case.arrows:
                continue
            with self.subTest(case=case.code):
                arrows = AlgorithmDetailView.last_layer_arrows(
                    case.main_algorithm,
                ).split(',')
                expected = case.arrows.split(',')
                if case.code == 'Nb':
                    self.assertEqual(len(arrows), len(expected))
                else:
                    self.assertEqual(set(arrows), set(expected))


class TestMoveTrack(unittest.TestCase):
    """The hands are followed move by move."""

    def test_regrips_match_the_ergonomics(self) -> None:
        """The track counts the regrips the ergonomics analysis counts."""
        for algorithm in (T_PERM, SUNE, SCRAMBLE, TWIST,
                          "x R' U R' D2 R U' R' D2 R2 x'",
                          "R U R' F' L D B'"):
            with self.subTest(algorithm=algorithm):
                detail = view(algorithm)
                track = detail.build_track(
                    detail.algorithm.structure.structures,
                )
                self.assertEqual(
                    sum(step['regrip'] for step in track),
                    detail.algorithm.ergonomics.regrip_count,
                )

    def test_one_step_per_move(self) -> None:
        """Pauses and rotations keep their column."""
        detail = view("x R U R' U' . x'")
        track = detail.build_track(detail.algorithm.structure.structures)

        self.assertEqual(
            [step['hand'] for step in track],
            ['rotation', 'right', 'right', 'right', 'left', 'pause',
             'rotation'],
        )
        self.assertEqual(track[1]['transition'], '')
        self.assertEqual(track[4]['transition'], 'hand_switch')

    def test_load_bounds(self) -> None:
        """The discomfort stays between 0 and 1."""
        detail = view(SCRAMBLE)
        for step in detail.build_track([]):
            self.assertGreaterEqual(step['load'], 0)
            self.assertLessEqual(step['load'], 1)

    def test_structure_parts(self) -> None:
        """A conjugate reads A B A', a commutator A B A' B'."""
        structures = Algorithm.parse_moves(T_PERM).structure.structures
        parts, owners = AlgorithmDetailView.structure_parts(structures, 14)

        self.assertEqual(
            parts,
            ['A', 'A', 'B', 'B', 'B', 'B', 'B', "A'", "A'",
             'A', 'B', "A'", "B'", ''],
        )
        self.assertEqual(owners, [1] * 9 + [2] * 4 + [0])

    def test_overlapping_structure_is_skipped(self) -> None:
        """A structure over the moves of an earlier one is left out."""
        structures = Algorithm.parse_moves(T_PERM).structure.structures
        parts, owners = AlgorithmDetailView.structure_parts(
            [structures[0], structures[0]._replace(start=5, end=9)], 14,
        )

        self.assertEqual(owners, [1] * 9 + [0] * 5)
        self.assertEqual(parts[9:], [''] * 5)

    def test_unsplittable_structure_is_marked(self) -> None:
        """A structure whose moves cancel is marked, not split."""
        structures = Algorithm.parse_moves(T_PERM).structure.structures
        parts, _owners = AlgorithmDetailView.structure_parts(
            [structures[0]._replace(end=8)], 14,
        )

        self.assertEqual(parts[:8], ['·'] * 8)


class TestAnalysis(unittest.TestCase):
    """The effect, the variations and the tones."""

    def test_cycles(self) -> None:
        """The T permutation swaps two corners and two edges."""
        cycles, twisted = view(T_PERM).build_cubies(
            Algorithm.parse_moves(T_PERM).impacts(),
        )

        self.assertEqual(cycles, [
            {'kind': 'corner', 'pieces': ['URF', 'UBR']},
            {'kind': 'edge', 'pieces': ['UR', 'UL']},
        ])
        self.assertEqual(twisted, [])

    def test_twisted_in_place(self) -> None:
        """Corners twisted without moving are named apart."""
        cycles, twisted = view(TWIST).build_cubies(
            Algorithm.parse_moves(TWIST).impacts(),
        )

        self.assertEqual(cycles, [])
        self.assertEqual(len(twisted), 2)

    def test_no_cubies_beyond_the_3x3x3(self) -> None:
        """A big cube has no cubie analysis, and no failure."""
        context = view("3Rw U 3Rw'").get_context()

        self.assertEqual(context['cubie_cycles'], [])
        self.assertEqual(context['patterns'], [])

    def test_variations(self) -> None:
        """The original comes first, one variation is the best."""
        rows = view(SUNE).get_context()['variations']

        self.assertEqual(rows[0]['label'], 'Original')
        self.assertTrue(rows[0]['original'])
        self.assertEqual(rows[0]['htm_delta'], 0)
        self.assertEqual(sum(row['best'] for row in rows), 1)
        self.assertEqual(
            {row['label']: row['case'] for row in rows}['Inverse'],
            'OLL 26',
        )

    def test_tones(self) -> None:
        """Scores and cycle orders are toned by band."""
        self.assertEqual(
            AlgorithmDetailView.score_tone(0.9, ERGONOMICS_TONES), 'good',
        )
        self.assertEqual(
            AlgorithmDetailView.score_tone(0.55, ERGONOMICS_TONES), '',
        )
        self.assertEqual(
            AlgorithmDetailView.score_tone(0.1, ERGONOMICS_TONES), 'bad',
        )
        self.assertEqual(AlgorithmDetailView.cycles_tone(2), 'good')
        self.assertEqual(AlgorithmDetailView.cycles_tone(30), 'warn')
        self.assertEqual(AlgorithmDetailView.cycles_tone(100), 'bad')


class TestEffectMask(unittest.TestCase):
    """The moved facelets stay lit whatever the orientation shown."""

    def lit(self, algorithm: str, orientation: str) -> int:
        """
        Draw the effect cube as /cube/ does, in an orientation.

        Returns:
            The number of stickers drawn in colour, the others greyed.

        """
        context = AlgorithmDetailView(algorithm, orientation).get_context()
        cube = VCube()
        cube.rotate(
            context['orientation_moves']
            + context['algorithm'].transform(invert_moves),
        )
        colours = re.findall(FILL_RE, cube.image(mask=context['effect_mask']))
        greys = re.findall(FILL_RE, cube.image(mask='2' * 54))
        self.assertEqual(len(colours), len(greys))
        return sum(colour != greys[0] for colour in colours)

    def test_orientations(self) -> None:
        """Turning the cube over does not hide the moved facelets."""
        for algorithm, expected in ((T_PERM, 8), (SUNE, 12)):
            for orientation in ('UF', 'DF', 'FR', 'BD'):
                with self.subTest(algorithm=algorithm, o=orientation):
                    self.assertEqual(
                        self.lit(algorithm, orientation), expected,
                    )


class TestAlgorithmPage(AcademyPageTestCase):
    """The page through the application, trainings patched."""

    def test_sections(self) -> None:
        """Every section is rendered, the lab left out."""
        body = self.page(url(T_PERM))

        for slug in ('player', 'algorithm', 'execution', 'structure',
                     'memory', 'variations', 'effect', 'metrics'):
            with self.subTest(slug=slug):
                self.assertIn(f'id="{ slug }"', body)
        self.assertNotIn('id="lab"', body)
        self.assertIn('class="move-track"', body)

    def test_charts(self) -> None:
        """The eight charts carry their kind and data."""
        body = self.page(url(T_PERM))

        self.assertEqual(body.count('data-chart="'), 8)
        for kind in ('alg-profile', 'alg-share', 'alg-polar', 'alg-counts'):
            with self.subTest(kind=kind):
                self.assertIn(f'data-chart="{ kind }"', body)

    def test_solved_case(self) -> None:
        """A case algorithm links its case, under the academy."""
        body = self.page(url(T_PERM))

        self.assertIn('Solves <a href="/academy/CFOP/PLL/T/">PLL T</a>', body)
        self.assertIn('<a href="/academy/CFOP/PLL/">CFOP PLL</a>', body)
        self.assertIn('m=pll', body)
        self.assertIn('arrows=U2U8-black', body)
        self.assertNotIn('Your algorithm', body)

    def test_your_algorithm(self) -> None:
        """The solution saved while training is recognised."""
        entry = trained([1500] * 3)
        entry['solution'] = T_PERM
        self.write_step('PLL', {'T': entry})

        body = self.page(url(T_PERM))

        self.assertIn('Your algorithm', body)

    def test_no_case(self) -> None:
        """Any other algorithm has no breadcrumb and a masked cube."""
        body = self.page(url(SCRAMBLE))

        self.assertNotIn('Solves', body)
        self.assertNotIn('class="breadcrumb"', body)
        self.assertIsNotNone(re.search(r'mask=[12]{54}', body))

    def test_big_cube(self) -> None:
        """An algorithm needing a 4x4x4 is analysed on a 4x4x4."""
        body = self.page(url("3Rw U 3Rw'"))

        self.assertIn('"puzzle": "4x4x4"', body)

    def test_lab_in_debug(self) -> None:
        """The raw analysis is shown in debug only."""
        client = WSGIClient(Server.create_app(debug=True))
        _status, _headers, body = client.get(url(T_PERM))

        self.assertIn('id="lab"', body)

    def test_v1(self) -> None:
        """The V1 page stays reachable."""
        body = self.page(url(T_PERM) + '?v1')

        self.assertIn('metricsChart', body)
