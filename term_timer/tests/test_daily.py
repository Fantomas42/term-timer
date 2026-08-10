"""Tests for the daily scramble command."""
import asyncio
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer import stats as stats_mod
from term_timer.arguments import get_parser
from term_timer.in_out import save_solves
from term_timer.interface.console import theme as console_theme
from term_timer.scripts.commands import daily as daily_mod
from term_timer.scripts.commands import session as session_mod
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter

SHORT_SCRAMBLE = "L2 D' L' F' L'"
SHORT_MOVES = 'L@0 F@507 L@1019 D@1768 L@2518 L@2608'
DAY = '2026-08-09'


def make_solve(
        date: int = 1766883476,
        time: int = 2608404439,
        *,
        flag: str = '',
) -> Solve:
    """
    Build a Solve fixture on the daily scramble.

    Returns:
        A configured Solve instance.

    """
    solve = Solve(
        date, time, SHORT_SCRAMBLE, moves=SHORT_MOVES, flag=flag,  # type: ignore[arg-type]
    )
    solve.method_name = 'cfop'
    solve.orientation = 'auto'
    return solve


class TestParseDate(unittest.TestCase):
    """Tests for the date argument of the daily command."""

    def test_empty_is_today(self) -> None:
        """An unset date runs the scramble of the day."""
        self.assertEqual(daily_mod.parse_date(''), date.today())  # noqa: DTZ011

    def test_explicit_date(self) -> None:
        """A date is read as YYYY-MM-DD."""
        self.assertEqual(daily_mod.parse_date(DAY), date(2026, 8, 9))

    def test_invalid_date(self) -> None:
        """An unparsable date raises."""
        with self.assertRaises(ValueError):
            daily_mod.parse_date('yesterday')


class TestDailyReview(unittest.TestCase):
    """Tests for the review and detail handlers of the daily command."""

    def setUp(self) -> None:
        """Point the daily directory at a temporary folder."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        patcher = patch.object(
            daily_mod, 'DAILY_DIRECTORY', self.directory,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a daily command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['daily', '-d', DAY, *args])

    def run_command(self, *args: str) -> tuple[int, str]:
        """
        Run a daily command on the stored day.

        Returns:
            The exit code and the rendered output.

        """
        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        options = self.parse(*args)
        with (
                patch.object(session_mod, 'console', recorder),
                patch.object(daily_mod, 'console', recorder),
                patch.object(stats_mod, 'console', recorder),
        ):
            code = asyncio.run(daily_mod.daily(options))

        return code, recorder.export_text()

    def store_attempts(self) -> None:
        """Store two attempts on the daily scramble."""
        save_solves(
            3,
            DAY,
            [make_solve(), make_solve(date=1766883500, time=1_000_000_000)],
            directory=self.directory,
        )

    def test_review_without_attempts(self) -> None:
        """Reviewing a day with no solve warns."""
        code, output = self.run_command('-r')

        self.assertEqual(code, 1)
        self.assertIn(DAY, output)

    def test_review_lists_the_attempts(self) -> None:
        """The review lists the attempts backing its statistics."""
        self.store_attempts()

        code, output = self.run_command('-r')

        self.assertEqual(code, 0)
        self.assertIn(f'Daily summary for { DAY }', output)
        self.assertIn('Attempts', output)
        self.assertIn('#2', output)

    def test_review_lists_between_summary_and_graph(self) -> None:
        """The listing sits between the statistics and the graph."""
        self.store_attempts()

        manager = Mock()
        with (
                patch.object(
                    SolveStatisticsReporter, 'print_summary',
                    manager.print_summary,
                ),
                patch.object(
                    SolveStatisticsReporter, 'attempts_listing',
                    manager.attempts_listing,
                ),
                patch.object(
                    SolveStatisticsReporter, 'graph', manager.graph,
                ),
        ):
            self.run_command('-r')

        self.assertEqual(
            [name for name, _args, _kwargs in manager.mock_calls],
            ['print_summary', 'attempts_listing', 'graph'],
        )

    def test_detail_shows_a_single_attempt(self) -> None:
        """--detail prints the detail alone, without the review."""
        self.store_attempts()

        code, output = self.run_command('-n', '2')

        self.assertEqual(code, 0)
        self.assertIn('Detail for 3x3x3 #2', output)
        self.assertNotIn('Attempts', output)
        self.assertNotIn('Daily summary', output)

    def test_detail_of_several_attempts(self) -> None:
        """--detail takes more than one id."""
        self.store_attempts()

        code, output = self.run_command('-n', '1', '2')

        self.assertEqual(code, 0)
        self.assertIn('Detail for 3x3x3 #1', output)
        self.assertIn('Detail for 3x3x3 #2', output)

    def test_detail_of_an_unknown_attempt(self) -> None:
        """An id naming no attempt is reported."""
        self.store_attempts()

        code, output = self.run_command('-n', '9')

        self.assertEqual(code, 1)
        self.assertIn('Invalid solve #9', output)

    def test_detail_keeps_the_valid_ids(self) -> None:
        """An unusable id does not withhold the details that resolve."""
        self.store_attempts()

        code, output = self.run_command('-n', '0', '1')

        self.assertEqual(code, 1)
        self.assertIn('Invalid solve #0', output)
        self.assertIn('Detail for 3x3x3 #1', output)

    def test_detail_without_attempts(self) -> None:
        """Detailing a day with no solve warns."""
        code, _output = self.run_command('-n', '1')

        self.assertEqual(code, 1)


class TestDailySummary(unittest.TestCase):
    """Tests for the participation summary of the daily command."""

    def test_summary_without_solves(self) -> None:
        """An empty daily library reports nothing recorded."""
        with patch.object(
                daily_mod, 'load_all_daily_solves', return_value=[],
        ):
            self.assertEqual(daily_mod.daily_summary(3), 1)

    def test_summary_wins_over_review(self) -> None:
        """--summary is answered before --review."""
        options = get_parser().parse_args(['daily', '-l', '-r', '-n', '1'])
        with patch.object(
                daily_mod, 'daily_summary', return_value=0,
        ) as summary:
            self.assertEqual(asyncio.run(daily_mod.daily(options)), 0)

        summary.assert_called_once_with(3)
