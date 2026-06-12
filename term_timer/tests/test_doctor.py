"""Tests for solve diagnostics grouping."""
import unittest

from term_timer.doctor import Diagnostic
from term_timer.doctor import DiagnosticCategory
from term_timer.doctor import DiagnosticSeverity
from term_timer.doctor import group_solve_diagnostics


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


if __name__ == '__main__':
    unittest.main()
