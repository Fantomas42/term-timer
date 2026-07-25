"""Tests for the doctor report reporter."""
import unittest
from typing import TYPE_CHECKING
from typing import cast

from term_timer.doctor import DiagnosticCategory
from term_timer.doctor import DiagnosticSeverity
from term_timer.interface.doctor import DoctorReporter

if TYPE_CHECKING:
    from term_timer.annotations import DoctorReport
    from term_timer.doctor import DoctorFinding


def make_finding(**overrides: object) -> 'DoctorFinding':
    """
    Build a minimal doctor finding for report rendering tests.

    Args:
        overrides: Finding fields to override.

    Returns:
        A finding with the given attributes.

    """
    finding: dict[str, object] = {
        'location': 'global',
        'category': DiagnosticCategory.EXECUTION_PAUSES,
        'metric_name': 'execution_pause_percent',
        'severity': DiagnosticSeverity.CRITICAL,
        'count': 5,
        'frequency': 0.5,
        'impact_per_solve': 3.0,
        'typical_value': 20.0,
        'expected_value': (10.0, 15.0),
        'recommendation': 'Practice slow solves. Never stop turning.',
        'command': '',
    }
    finding.update(overrides)

    return cast('DoctorFinding', finding)


def make_reporter(
        findings: 'list[DoctorFinding]',
        total: int = 10,
) -> DoctorReporter:
    """
    Build a reporter with preset results.

    Args:
        findings: Findings to render.
        total: Diagnosed solves count.

    Returns:
        Reporter ready for report rendering.

    """
    results: DoctorReport = {'total': total, 'findings': findings}

    return DoctorReporter(results)


class TestDoctorReporter(unittest.TestCase):
    """Tests for DoctorReporter report rendering."""

    def test_report_no_findings(self) -> None:
        """A window without findings reports sane solves."""
        report = make_reporter([]).report()

        self.assertIn('Diagnostics on last 10 solves:', report)
        self.assertIn('No issue detected, sane solves !', report)

    def test_report_finding_rendering(self) -> None:
        """A finding renders label, typical value, norm and stats."""
        report = make_reporter([make_finding()]).report()

        self.assertIn('[examen] Global [/examen]', report)
        self.assertIn('[title]3.00s/solve[/title]', report)
        self.assertIn('Pauses, typically 20.0% (norm 10%)', report)
        self.assertIn('[critical][CRITICAL][/critical]', report)
        self.assertIn('3.00s/solve on 50% of solves', report)

    def test_report_group_command(self) -> None:
        """The group header carries the first finding command."""
        finding = make_finding(
            location='PLL',
            command='term-timer train -s pll',
        )

        report = make_reporter([finding]).report()

        self.assertIn('[examen] PLL [/examen]', report)
        self.assertIn('[localhost]term-timer train -s pll[/localhost]',
                      report)

    def test_report_norm_high_for_recognition(self) -> None:
        """Recognition metrics display the top of their norm range."""
        finding = make_finding(
            location='PLL',
            category=DiagnosticCategory.RECOGNITION_SLOW,
            metric_name='step_recognition_percent',
            typical_value=31.0,
            expected_value=(5.0, 10.0),
        )

        report = make_reporter([finding]).report()

        self.assertIn('Recognition, typically 31.0% (norm 10%)', report)

    def test_report_zero_ideal_without_norm(self) -> None:
        """Zero-ideal categories display the count without norm."""
        finding = make_finding(
            category=DiagnosticCategory.AUFS_EXCESSIVE,
            metric_name='aufs',
            typical_value=7.0,
            expected_value=(0.0, 6.0),
        )

        report = make_reporter([finding]).report()

        self.assertIn('AUF adjustments, typically 7 QTM', report)
        self.assertNotIn('(norm', report)

    def test_report_focus_section(self) -> None:
        """The focus section lists top findings with recommendations."""
        findings = [
            make_finding(
                impact_per_solve=3.0,
                command='term-timer train -s ll',
            ),
            make_finding(
                location='F2L',
                category=DiagnosticCategory.PLANNING_LOOKAHEAD,
                metric_name='step_recognition_percent',
                impact_per_solve=1.0,
            ),
        ]

        report = make_reporter(findings).report()

        self.assertIn('[stats]Focus:[/stats]', report)
        self.assertIn('1. Pauses @ Global', report)
        self.assertIn('2. Lookahead @ F2L', report)
        self.assertIn(
            '[localhost]term-timer train -s ll[/localhost]', report,
        )
        self.assertIn(
            'Practice slow solves.\n     Never stop turning.', report,
        )

    def test_report_trend_markers(self) -> None:
        """Trend markers flag worsened, improved, flat and new findings."""
        current = [
            make_finding(impact_per_solve=3.0),
            make_finding(
                category=DiagnosticCategory.EXECUTION_SPEED,
                metric_name='tps',
                typical_value=2.1,
                expected_value=2.5,
                impact_per_solve=1.0,
            ),
            make_finding(
                category=DiagnosticCategory.EXECUTION_FLUENCY,
                metric_name='fluency',
                typical_value=55.0,
                expected_value=(60.0, 100.0),
                impact_per_solve=0.5,
            ),
            make_finding(
                category=DiagnosticCategory.EFFICIENCY_MOVECOUNT,
                metric_name='step_missed_moves',
                typical_value=6.0,
                expected_value=0.0,
                impact_per_solve=0.4,
            ),
        ]
        previous: DoctorReport = {
            'total': 10,
            'findings': [
                make_finding(impact_per_solve=2.0),
                make_finding(
                    category=DiagnosticCategory.EXECUTION_SPEED,
                    metric_name='tps',
                    impact_per_solve=2.0,
                ),
                make_finding(
                    category=DiagnosticCategory.EXECUTION_FLUENCY,
                    metric_name='fluency',
                    impact_per_solve=0.51,
                ),
                make_finding(
                    location='PLL',
                    category=DiagnosticCategory.RECOGNITION_SLOW,
                    metric_name='step_recognition_percent',
                    impact_per_solve=1.5,
                ),
            ],
        }

        report = make_reporter(current).report(previous)

        self.assertIn('[trend-down]▲ +1.00s[/trend-down]', report)
        self.assertIn('[trend-up]▼ -1.00s[/trend-up]', report)
        self.assertIn('[trend-flat]=[/trend-flat]', report)
        self.assertIn('[trend-down]new[/trend-down]', report)
        self.assertIn('[success]Resolved: Recognition (PLL)[/success]',
                      report)

    def test_report_without_previous_has_no_trend(self) -> None:
        """Without a previous report no trend marker is rendered."""
        report = make_reporter([make_finding()]).report()

        self.assertNotIn('trend-', report)
        self.assertNotIn('Resolved:', report)
