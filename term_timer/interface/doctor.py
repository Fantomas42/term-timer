"""Doctor report rendering for diagnostics aggregated over solves."""
from typing import Final

from term_timer.annotations import DoctorReport
from term_timer.doctor import CATEGORY_LABELS
from term_timer.doctor import NORM_HIGH_METRICS
from term_timer.doctor import ZERO_IDEAL_CATEGORIES
from term_timer.doctor import DoctorFinding
from term_timer.doctor import group_doctor_findings
from term_timer.formatter import format_metric

FOCUS_COUNT: Final = 3
TREND_EPSILON: Final = 0.05


class DoctorReporter:
    """
    Renders a doctor report as rich-formatted text.

    Consumes a plain ``DoctorReport`` so the same rendering serves the
    doctor command and any other display of aggregated diagnostics,
    independently of how the report was produced.
    """

    def __init__(self, results: DoctorReport) -> None:
        """Initialize the reporter with the report to render."""
        self.results = results

    @staticmethod
    def finding_title(finding: DoctorFinding) -> str:
        """
        Build the constat line of a finding.

        Returns:
            Category label with typical value, and norm when the ideal
            is not evidently zero.

        """
        label = CATEGORY_LABELS[finding['category']]
        typical = format_metric(
            finding['metric_name'], finding['typical_value'],
        )

        if finding['category'] in ZERO_IDEAL_CATEGORIES:
            return f'{ label }, typically { typical }'

        expected = finding['expected_value']
        metric_name = finding['metric_name']
        if isinstance(expected, tuple):
            norm = (
                expected[1]
                if metric_name in NORM_HIGH_METRICS
                else expected[0]
            )
        else:
            norm = expected
        unit = (
            '%'
            if metric_name == 'fluency' or metric_name.endswith('percent')
            else ''
        )

        return (
            f'{ label }, typically { typical } (norm { norm:g}{ unit })'
        )

    @staticmethod
    def trend_tag(
        finding: DoctorFinding,
        prior: DoctorFinding | None,
    ) -> str:
        """
        Build the trend marker of a finding against the previous window.

        Returns:
            Rich-formatted delta of impact per solve, or a new marker.

        """
        if prior is None:
            return '[trend-down]new[/trend-down]'

        delta = finding['impact_per_solve'] - prior['impact_per_solve']
        if abs(delta) < TREND_EPSILON:
            return '[trend-flat]=[/trend-flat]'
        if delta > 0:
            return f'[trend-down]▲ +{ delta:.2f}s[/trend-down]'

        return f'[trend-up]▼ { delta:.2f}s[/trend-up]'

    def finding_lines(
        self,
        finding: DoctorFinding,
        prior: DoctorFinding | None,
        *,
        trend: bool,
    ) -> list[str]:
        """
        Build the display lines of a single finding.

        Returns:
            Constat line and severity/frequency/impact line.

        """
        stat_line = (
            f'     [{ finding["severity"] }]'
            f'[{ finding["severity"].upper() }]'
            f'[/{ finding["severity"] }] '
            f'[context]{ finding["impact_per_solve"]:.2f}s/solve '
            f'on { finding["frequency"]:.0%} of solves[/context]'
        )
        if trend:
            stat_line += f' { self.trend_tag(finding, prior) }'

        return [
            (
                f'  [diagnostic] - { self.finding_title(finding) }'
                '[/diagnostic]'
            ),
            stat_line,
        ]

    @staticmethod
    def focus_lines(findings: list[DoctorFinding]) -> list[str]:
        """
        Build the focus section listing the top improvement levers.

        Returns:
            Rich-formatted lines with recommendations and commands.

        """
        lines = ['[stats]Focus:[/stats]']

        for rank, finding in enumerate(
                findings[:FOCUS_COUNT], start=1,
        ):
            location = finding['location']
            place = 'Global' if location == 'global' else location
            headline = (
                f'  [diagnostic] { rank }. '
                f'{ CATEGORY_LABELS[finding["category"]] } '
                f'@ { place }[/diagnostic] '
                f'[title]{ finding["impact_per_solve"]:.2f}s/solve[/title]'
            )
            if finding['command']:
                headline += (
                    f' [localhost]{ finding["command"] }[/localhost]'
                )
            lines.extend((
                headline,
                '  [advice]   ' +
                finding['recommendation'].replace('. ', '.\n     ') +
                '[/advice]',
            ))

        return lines

    def report(
            self,
            previous: DoctorReport | None = None,
            *,
            subject: str = '',
    ) -> str:
        """
        Generate the aggregated diagnostics report.

        Args:
            previous: Report of the preceding window of solves, enabling
                trend markers and the resolved findings line.
            subject: What the diagnosed window is, named in the header.
                Defaults to the last solves, what a window of a session
                of varied scrambles is.

        Returns:
            Rich-formatted report string.

        """
        findings = self.results['findings']
        subject = subject or f'last { self.results["total"] } solves'
        lines = [
            f'[stats]Diagnostics on { subject }:[/stats]',
        ]

        if not findings:
            lines.append(
                '[success] - No issue detected, sane solves ![/success]',
            )
            return '\n'.join(lines)

        priors: dict[tuple[str, str], DoctorFinding] = {}
        if previous is not None:
            priors = {
                (item['location'], item['category']): item
                for item in previous['findings']
            }

        for group in group_doctor_findings(findings):
            location = group['location']
            title = 'Global' if location == 'global' else location

            section_line = (
                f'[examen] { title } [/examen] '
                f'[title]{ group["impact_per_solve"]:.2f}s/solve[/title]'
            )
            if group['command']:
                section_line += (
                    f' [localhost]{ group["command"] }[/localhost]'
                )
            lines.append(section_line)

            for finding in group['findings']:
                key = (finding['location'], finding['category'])
                lines.extend(
                    self.finding_lines(
                        finding,
                        priors.pop(key, None),
                        trend=previous is not None,
                    ),
                )

        if priors:
            resolved = ' · '.join(
                f'{ CATEGORY_LABELS[item["category"]] } '
                f'({ item["location"] })'
                for item in priors.values()
            )
            lines.append(f'[success]Resolved: { resolved }[/success]')

        lines.extend(self.focus_lines(findings))

        return '\n'.join(lines)
