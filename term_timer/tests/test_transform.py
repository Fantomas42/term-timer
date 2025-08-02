import unittest

from cubing_algs.parsing import parse_moves

from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves


class TransformSliceTestCase(unittest.TestCase):

    def test_reslice_moves_issue_01(self):
        provide = parse_moves("B' F B' F U L R' R' L D' L' R U D' D' U R L' U")
        expect = parse_moves("S2 D M2 D' M' S2 M U")

        result = prettify_moves(
            humanize_moves(provide),
        )

        self.assertEqual(
            result,
            expect,
        )
