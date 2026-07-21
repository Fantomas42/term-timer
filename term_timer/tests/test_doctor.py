"""Tests for solve diagnostics grouping."""
import unittest
from typing import cast

from term_timer.doctor import Diagnostic
from term_timer.doctor import DiagnosticCategory
from term_timer.doctor import DiagnosticSeverity
from term_timer.doctor import DoctorFinding
from term_timer.doctor import aggregate_solve_diagnostics
from term_timer.doctor import generate_solve_diagnostics
from term_timer.doctor import group_doctor_findings
from term_timer.doctor import group_solve_diagnostics
from term_timer.doctor import modal_diagnostic_severity
from term_timer.doctor import typical_expected_value
from term_timer.solve import Solve


def make_diagnostic(
        location: str,
        impact_seconds: float,
        command: str = '',
        **overrides: object,
) -> Diagnostic:
    """
    Build a minimal diagnostic for grouping and aggregation tests.

    Args:
        location: Where the issue occurs ('global' or step name).
        impact_seconds: Estimated potential time improvement.
        command: Command to practice this issue.
        overrides: Other diagnostic fields to override.

    Returns:
        A diagnostic with the given attributes.

    """
    diagnostic: dict[str, object] = {
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
    diagnostic.update(overrides)

    return cast('Diagnostic', diagnostic)


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


class ModalDiagnosticSeverityTestCase(unittest.TestCase):
    """Tests for modal_diagnostic_severity."""

    def test_most_frequent_severity_wins(self) -> None:
        """The severity firing most often is the modal one."""
        diagnostics = [
            make_diagnostic('global', 1.0,
                            severity=DiagnosticSeverity.MEDIUM),
            make_diagnostic('global', 1.0,
                            severity=DiagnosticSeverity.MEDIUM),
            make_diagnostic('global', 1.0,
                            severity=DiagnosticSeverity.CRITICAL),
        ]

        self.assertEqual(
            modal_diagnostic_severity(diagnostics),
            DiagnosticSeverity.MEDIUM,
        )

    def test_ties_resolved_by_most_severe(self) -> None:
        """On a frequency tie the most severe level wins."""
        diagnostics = [
            make_diagnostic('global', 1.0,
                            severity=DiagnosticSeverity.MEDIUM),
            make_diagnostic('global', 1.0,
                            severity=DiagnosticSeverity.HIGH),
        ]

        self.assertEqual(
            modal_diagnostic_severity(diagnostics),
            DiagnosticSeverity.HIGH,
        )


class TypicalExpectedValueTestCase(unittest.TestCase):
    """Tests for typical_expected_value."""

    def test_scalar_values_median(self) -> None:
        """Scalar expected values reduce to their median."""
        self.assertEqual(typical_expected_value([2.5, 2.5, 3.0]), 2.5)

    def test_range_values_median_by_bound(self) -> None:
        """Range expected values are medianed bound by bound."""
        self.assertEqual(
            typical_expected_value([(6.0, 8.0), (10.0, 12.0), (7.0, 9.0)]),
            (7.0, 9.0),
        )


class AggregateSolveDiagnosticsTestCase(unittest.TestCase):
    """Tests for aggregate_solve_diagnostics."""

    def test_empty_window(self) -> None:
        """An empty window produces no findings."""
        self.assertEqual(aggregate_solve_diagnostics([]), [])

    def test_single_solve_single_finding(self) -> None:
        """A lone diagnostic maps to one full-frequency finding."""
        diagnostic = make_diagnostic(
            'global', 2.0, 'term-timer train -s ll',
            actual_value=1.2,
        )

        findings = aggregate_solve_diagnostics([[diagnostic]])

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding['location'], 'global')
        self.assertEqual(
            finding['category'], DiagnosticCategory.EXECUTION_SPEED,
        )
        self.assertEqual(finding['metric_name'], 'tps')
        self.assertEqual(finding['severity'], DiagnosticSeverity.MEDIUM)
        self.assertEqual(finding['count'], 1)
        self.assertEqual(finding['frequency'], 1.0)
        self.assertAlmostEqual(finding['impact_per_solve'], 2.0)
        self.assertEqual(finding['typical_value'], 1.2)
        self.assertEqual(finding['expected_value'], 2.0)
        self.assertEqual(finding['recommendation'], 'Recommendation')
        self.assertEqual(finding['command'], 'term-timer train -s ll')

    def test_frequency_counts_affected_solves(self) -> None:
        """Solves without the diagnostic dilute frequency and impact."""
        findings = aggregate_solve_diagnostics([
            [make_diagnostic('global', 3.0)],
            [],
            [],
        ])

        finding = findings[0]
        self.assertEqual(finding['count'], 1)
        self.assertAlmostEqual(finding['frequency'], 1 / 3)
        self.assertAlmostEqual(finding['impact_per_solve'], 1.0)

    def test_location_and_category_split_findings(self) -> None:
        """Distinct locations or categories produce distinct findings."""
        findings = aggregate_solve_diagnostics([
            [
                make_diagnostic(
                    'global', 1.0,
                    category=DiagnosticCategory.EXECUTION_SPEED,
                ),
                make_diagnostic(
                    'global', 1.0,
                    category=DiagnosticCategory.EXECUTION_PAUSES,
                ),
                make_diagnostic(
                    'OLL', 1.0,
                    category=DiagnosticCategory.EXECUTION_FLUENCY,
                ),
            ],
        ])

        self.assertEqual(len(findings), 3)
        self.assertEqual(
            {
                (finding['location'], finding['category'])
                for finding in findings
            },
            {
                ('global', DiagnosticCategory.EXECUTION_SPEED),
                ('global', DiagnosticCategory.EXECUTION_PAUSES),
                ('OLL', DiagnosticCategory.EXECUTION_FLUENCY),
            },
        )

    def test_findings_sorted_by_impact_per_solve(self) -> None:
        """Findings are ranked by expected gain per solve, not frequency."""
        rare_but_heavy = [
            [make_diagnostic(
                'Cross', 4.0,
                category=DiagnosticCategory.PLANNING_CROSS,
            )],
            [make_diagnostic('global', 0.5)],
            [make_diagnostic('global', 0.5)],
            [make_diagnostic('global', 0.5)],
        ]

        findings = aggregate_solve_diagnostics(rare_but_heavy)

        self.assertEqual(
            [finding['location'] for finding in findings],
            ['Cross', 'global'],
        )
        self.assertAlmostEqual(findings[0]['impact_per_solve'], 1.0)
        self.assertAlmostEqual(findings[1]['impact_per_solve'], 0.375)
        self.assertAlmostEqual(findings[1]['frequency'], 0.75)

    def test_typical_value_is_median(self) -> None:
        """The typical value is the median of measured values."""
        findings = aggregate_solve_diagnostics([
            [make_diagnostic('global', 1.0, actual_value=1.0)],
            [make_diagnostic('global', 1.0, actual_value=1.4)],
            [make_diagnostic('global', 1.0, actual_value=9.9)],
        ])

        self.assertEqual(findings[0]['typical_value'], 1.4)

    def test_recommendation_follows_modal_severity(self) -> None:
        """The recommendation comes from the modal severity tier."""
        findings = aggregate_solve_diagnostics([
            [make_diagnostic(
                'global', 1.0,
                severity=DiagnosticSeverity.CRITICAL,
                recommendation='Critical advice',
            )],
            [make_diagnostic(
                'global', 1.0,
                severity=DiagnosticSeverity.MEDIUM,
                recommendation='Medium advice',
            )],
            [make_diagnostic(
                'global', 1.0,
                severity=DiagnosticSeverity.MEDIUM,
                recommendation='Medium advice',
            )],
        ])

        self.assertEqual(findings[0]['severity'], DiagnosticSeverity.MEDIUM)
        self.assertEqual(findings[0]['recommendation'], 'Medium advice')

    def test_command_is_most_frequent(self) -> None:
        """A recurring per-case command surfaces at aggregate level."""
        findings = aggregate_solve_diagnostics([
            [make_diagnostic('OLL', 1.0, 'term-timer train -s oll -c "35"')],
            [make_diagnostic('OLL', 1.0, 'term-timer train -s oll -c "35"')],
            [make_diagnostic('OLL', 1.0, 'term-timer train -s oll -c "27"')],
        ])

        self.assertEqual(
            findings[0]['command'],
            'term-timer train -s oll -c "35"',
        )

    def test_expected_value_range_median(self) -> None:
        """Range expected values stay ranges in the finding."""
        findings = aggregate_solve_diagnostics([
            [make_diagnostic('OLL', 1.0, expected_value=(6.0, 10.0))],
            [make_diagnostic('OLL', 1.0, expected_value=(8.0, 12.0))],
        ])

        self.assertEqual(findings[0]['expected_value'], (7.0, 11.0))


def make_findings() -> list[DoctorFinding]:
    """
    Build findings on two locations for grouping tests.

    Returns:
        Findings sorted by impact per solve.

    """
    return aggregate_solve_diagnostics([
        [
            make_diagnostic(
                'Cross', 2.0, 'term-timer train -s cross',
                category=DiagnosticCategory.PLANNING_CROSS,
            ),
            make_diagnostic(
                'Cross', 1.0,
                category=DiagnosticCategory.EXECUTION_FLUENCY,
            ),
            make_diagnostic('global', 2.5),
        ],
    ])


class GroupDoctorFindingsTestCase(unittest.TestCase):
    """Tests for group_doctor_findings."""

    def test_empty_findings(self) -> None:
        """An empty finding list produces no groups."""
        self.assertEqual(group_doctor_findings([]), [])

    def test_groups_by_location_sorted_by_impact(self) -> None:
        """Findings sharing a location merge, groups rank by impact."""
        groups = group_doctor_findings(make_findings())

        self.assertEqual(
            [group['location'] for group in groups],
            ['Cross', 'global'],
        )
        self.assertAlmostEqual(groups[0]['impact_per_solve'], 3.0)
        self.assertEqual(len(groups[0]['findings']), 2)
        self.assertAlmostEqual(groups[1]['impact_per_solve'], 2.5)

    def test_group_command_first_non_empty(self) -> None:
        """The group command is the first non-empty finding command."""
        groups = group_doctor_findings(make_findings())

        self.assertEqual(groups[0]['command'], 'term-timer train -s cross')


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
