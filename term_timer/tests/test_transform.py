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


class TransformHumanizeTestCase(unittest.TestCase):

    def test_humanize_moves_issue_01(self):
        provide = parse_moves(
            "R'@23249 L@23279 "
            "R'@23520 L@23520 "
            "U@23789 "
            "B@24060 F'@24060 "
            "F'@24300 B@24301 "
            "D'@24809 "
            "B'@25499 F@25529 "
            "U@26309 D'@26311 "
            "D'@26639 U@26640 "
            "F@27089 B'@27090",
        )

        expect = parse_moves("M2 D S2 D' S M2 S'")

        result = prettify_moves(
            humanize_moves(provide),
        )

        self.assertEqual(
            result,
            expect,
        )
