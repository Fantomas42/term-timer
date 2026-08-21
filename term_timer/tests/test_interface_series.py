"""Tests for the SeriesReporter rolling-average rendering mixin."""
import unittest

from rich.console import Console as RichConsole

from term_timer.interface.series import SeriesReporter
from term_timer.stats import Statistics


class TestSeriesStyle(unittest.TestCase):
    """Tests for SeriesReporter.series_style."""

    def test_known_token(self) -> None:
        """A token with a dedicated theme style keeps it."""
        self.assertEqual(SeriesReporter.series_style('ao5'), 'ao5')

    def test_preset_token(self) -> None:
        """A csTimer preset token now has a dedicated style."""
        self.assertEqual(SeriesReporter.series_style('ao50'), 'ao50')

    def test_unknown_token_falls_back(self) -> None:
        """A token without a dedicated style uses the fallback."""
        self.assertEqual(SeriesReporter.series_style('ao7'), 'average')


class TestSeriesLabel(unittest.TestCase):
    """Tests for SeriesReporter.series_label."""

    def test_average_label(self) -> None:
        """An average label capitalises the kind."""
        self.assertEqual(SeriesReporter.series_label('ao', 5), 'Ao5')

    def test_mean_label(self) -> None:
        """A mean label capitalises the kind."""
        self.assertEqual(SeriesReporter.series_label('mo', 3), 'Mo3')


class TestFormatSeriesLine(unittest.TestCase):
    """Tests for SeriesReporter.format_series_line."""

    def test_first_solve_is_empty(self) -> None:
        """A single solve yields no inline line."""
        stats = Statistics([1000])
        self.assertEqual(
            SeriesReporter.format_series_line(stats, [('ao', 5)]), '',
        )

    def test_includes_reachable_entries(self) -> None:
        """Each reachable series entry is rendered with its style."""
        stats = Statistics([1000, 2000, 3000, 4000, 5000])
        line = SeriesReporter.format_series_line(
            stats, [('mo', 3), ('ao', 5)],
        )
        self.assertIn('[mo3]Mo3', line)
        self.assertIn('[ao5]Ao5', line)

    def test_skips_unreachable_entries(self) -> None:
        """Entries needing more solves than available are skipped."""
        stats = Statistics([1000, 2000])
        line = SeriesReporter.format_series_line(stats, [('ao', 5)])
        self.assertNotIn('Ao5', line)

    def test_suffix_appended(self) -> None:
        """A non-empty suffix is appended at the end of the line."""
        stats = Statistics([1000, 2000, 3000])
        line = SeriesReporter.format_series_line(
            stats, [('mo', 3)], suffix='TREND',
        )
        self.assertTrue(line.endswith('TREND'))

    def test_empty_suffix_ignored(self) -> None:
        """An empty suffix leaves the line untouched."""
        stats = Statistics([1000, 2000, 3000])
        line = SeriesReporter.format_series_line(
            stats, [('mo', 3)], suffix='',
        )
        self.assertFalse(line.endswith(' '))


class TestPrintSessionRecords(unittest.TestCase):
    """Tests for SeriesReporter.print_session_records."""

    @staticmethod
    def render(
            new_stats: Statistics,
            old_stats: Statistics,
            series: list[tuple[str, int]],
    ) -> str:
        """
        Capture the records output as plain text.

        Returns:
            The rendered records block as plain text.

        """
        reporter = SeriesReporter()
        reporter.console = RichConsole(record=True, width=80)
        reporter.counter = 6
        reporter.print_session_records(new_stats, old_stats, series)
        return reporter.console.export_text()

    def test_no_records_for_single_solve(self) -> None:
        """No record line is printed for the first solve."""
        new_stats = Statistics([1000])
        old_stats = Statistics([])
        self.assertEqual(self.render(new_stats, old_stats, [('mo', 3)]), '')

    def test_beaten_record_is_celebrated(self) -> None:
        """A beaten average prints its record line."""
        new_stats = Statistics([3000, 3000, 3000, 1000, 1000, 1000])
        old_stats = Statistics([3000, 3000, 3000, 1000, 1000])
        output = self.render(new_stats, old_stats, [('mo', 3)])
        self.assertIn('Best Mo3', output)

    def test_unbeaten_record_is_silent(self) -> None:
        """An average that ties or misses the best prints nothing."""
        new_stats = Statistics([3000, 3000, 3000])
        old_stats = Statistics([3000, 3000])
        self.assertEqual(self.render(new_stats, old_stats, [('mo', 3)]), '')

    def test_dnf_average_never_records(self) -> None:
        """A DNF average (value 0) is never treated as a record."""
        new_stats = Statistics([3000, 3000, 3000, 1000, 1000, 0])
        old_stats = Statistics([3000, 3000, 3000, 1000, 1000])
        output = self.render(new_stats, old_stats, [('mo', 3)])
        self.assertEqual(output, '')

    def test_unreachable_entry_skipped(self) -> None:
        """An average needing more solves than available is skipped."""
        new_stats = Statistics([1000, 2000])
        old_stats = Statistics([1000])
        output = self.render(new_stats, old_stats, [('ao', 5)])
        self.assertEqual(output, '')

    @staticmethod
    def collect(
            new_stats: Statistics,
            old_stats: Statistics,
            series: list[tuple[str, int]],
    ) -> list[tuple[str, int, int]]:
        """
        Collect the records the reporter found, ignoring the rendering.

        Returns:
            The broken records, as the reporter returns them.

        """
        reporter = SeriesReporter()
        reporter.console = RichConsole(record=True, width=80)
        reporter.counter = 6
        return reporter.print_session_records(new_stats, old_stats, series)

    def test_beaten_record_is_returned(self) -> None:
        """
        A celebrated record is also handed back to the caller.

        The event stream publishes what the line says, from the same
        comparison, instead of running the whole watch a second time.
        """
        new_stats = Statistics([3000, 3000, 3000, 1000, 1000, 1000])
        old_stats = Statistics([3000, 3000, 3000, 1000, 1000])
        records = self.collect(new_stats, old_stats, [('mo', 3)])

        self.assertEqual(len(records), 1)
        token, value, previous = records[0]
        self.assertEqual(token, 'mo3')
        self.assertLess(value, previous)

    def test_silent_watch_returns_nothing(self) -> None:
        """No line printed, no record handed back."""
        new_stats = Statistics([3000, 3000, 3000])
        old_stats = Statistics([3000, 3000])
        self.assertEqual(self.collect(new_stats, old_stats, [('mo', 3)]), [])

    def test_first_solve_returns_nothing(self) -> None:
        """The very first solve of a session breaks nothing."""
        new_stats = Statistics([1000])
        old_stats = Statistics([])
        self.assertEqual(self.collect(new_stats, old_stats, [('mo', 3)]), [])
