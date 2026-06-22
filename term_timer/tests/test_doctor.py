"""Tests for solve diagnostics grouping."""
import unittest

from term_timer.doctor import Diagnostic
from term_timer.doctor import DiagnosticCategory
from term_timer.doctor import DiagnosticSeverity
from term_timer.doctor import generate_solve_diagnostics
from term_timer.doctor import group_solve_diagnostics
from term_timer.solve import Solve


def make_diagnostic(
        location: str,
        impact_seconds: float,
        command: str = '',
) -> Diagnostic:
    """
    Build a minimal diagnostic for grouping tests.

    Args:
        location: Where the issue occurs ('global' or step name).
        impact_seconds: Estimated potential time improvement.
        command: Command to practice this issue.

    Returns:
        A diagnostic with the given location, impact and command.

    """
    return {
        'severity': DiagnosticSeverity.MEDIUM,
        'category': DiagnosticCategory.EXECUTION_SPEED,
        'impact_seconds': impact_seconds,
        'location': location,
        'metric_name': 'tps',
        'actual_value': 1.0,
        'expected_value': 2.0,
        'description': 'Description',
        'recommendation': 'Recommendation',
        'command': command,
    }


class GroupSolveDiagnosticsTestCase(unittest.TestCase):
    """Tests for group_solve_diagnostics."""

    def test_empty_diagnostics(self) -> None:
        """An empty diagnostic list produces no groups."""
        self.assertEqual(group_solve_diagnostics([]), [])

    def test_groups_by_location(self) -> None:
        """Diagnostics sharing a location are merged in a single group."""
        diagnostics = [
            make_diagnostic('global', 2.0),
            make_diagnostic('F2L', 1.5),
            make_diagnostic('global', 0.5),
        ]

        groups = group_solve_diagnostics(diagnostics)

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]['location'], 'global')
        self.assertEqual(len(groups[0]['diagnostics']), 2)
        self.assertEqual(groups[1]['location'], 'F2L')
        self.assertEqual(len(groups[1]['diagnostics']), 1)

    def test_groups_sorted_by_aggregated_impact(self) -> None:
        """Groups are sorted by their summed impact, highest first."""
        diagnostics = [
            make_diagnostic('global', 1.0),
            make_diagnostic('Cross', 0.8),
            make_diagnostic('Cross', 0.7),
        ]

        groups = group_solve_diagnostics(diagnostics)

        self.assertEqual(
            [group['location'] for group in groups],
            ['Cross', 'global'],
        )
        self.assertAlmostEqual(groups[0]['impact_seconds'], 1.5)
        self.assertAlmostEqual(groups[1]['impact_seconds'], 1.0)

    def test_group_command_first_non_empty(self) -> None:
        """The group command is the first non-empty diagnostic command."""
        diagnostics = [
            make_diagnostic('Cross', 1.0),
            make_diagnostic('Cross', 0.5, 'term-timer train -s cross'),
            make_diagnostic('Cross', 0.2, 'term-timer train -s cross-bis'),
        ]

        groups = group_solve_diagnostics(diagnostics)

        self.assertEqual(groups[0]['command'], 'term-timer train -s cross')

    def test_items_order_preserved_within_group(self) -> None:
        """Diagnostics keep their input order inside each group."""
        diagnostics = [
            make_diagnostic('PLL', 0.6),
            make_diagnostic('PLL', 0.3),
            make_diagnostic('PLL', 0.1),
        ]

        groups = group_solve_diagnostics(diagnostics)

        self.assertEqual(
            [
                item['impact_seconds']
                for item in groups[0]['diagnostics']
            ],
            [0.6, 0.3, 0.1],
        )


class GenerateSolveDiagnosticsMethodsTestCase(unittest.TestCase):
    """Diagnostics generation works across every analysis method."""

    scramble = "U B' U B2 D' R2 D' L2 R2 U F2 U B2 F' D2 U' R' F L' F"
    solution = """
    L'@0 R'@592 B'@842 F'@2293 U@3296 L'@3453 U'@3940 R'@4987 D@5182 R@5512
    D'@5826 R@6402 D@6710 R'@6885 D@7928 D@9204 D@9466 L'@10165 D'@10527
    L@10646 D'@11992 F'@13047 D'@13160 F@13301 D'@13484 R'@14014 D@14106
    R@14263 D@15942 F@17037 L@17216 D@17331 L'@17398 D'@17490 F'@17810
    D@18454 D@18857 L@19121 D'@19227 D'@19447 L'@19584 D'@19737 L@19829
    D'@19956 L'@20081 L@22766 R'@22768 R'@23038 L@23040 U@23413 R'@24270
    L@24278 R'@24538 L@24544 D@24848 D@25128 L@25858 R'@25860 L@26116
    R'@26118 U@26370 L@26756 R'@26758 L@26996 R'@26996
    """

    def make_solve(self, method_name: str) -> Solve:
        """
        Build a fully reconstructed solve analysed with the given method.

        Returns:
            A Solve with method_applied populated for diagnostics.

        """
        solve = Solve(
            1715018355,
            26996000000,
            self.scramble,
            moves=self.solution,
        )
        solve.method_name = method_name
        solve.orientation = 'RU'
        return solve

    def test_diagnostics_for_every_method(self) -> None:
        """generate_solve_diagnostics never raises whatever the method is."""
        for method_name in ('raw', 'lbl', 'cfop', 'cf4op'):
            with self.subTest(method=method_name):
                solve = self.make_solve(method_name)
                diagnostics = generate_solve_diagnostics(solve)
                self.assertIsInstance(diagnostics, list)
