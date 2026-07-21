"""Tests for the timer command helpers."""
import unittest
from typing import cast
from unittest import mock

from term_timer.constants import DOCTOR_SESSION_BASELINE_MIN
from term_timer.scripts.commands.timer import print_session_doctor
from term_timer.solve import Solve


def analysable_solves(count: int, *, analysable: bool = True) -> list[Solve]:
    """
    Build a list of solve stand-ins with an analysable flag.

    Args:
        count: Number of solves to build.
        analysable: Value of the analysable attribute on each solve.

    Returns:
        A list of mock solves.

    """
    return [
        cast('Solve', mock.Mock(analysable=analysable))
        for _ in range(count)
    ]


def report_previous(round_size: int, history_size: int) -> object:
    """
    Run print_session_doctor and capture the trend baseline used.

    Args:
        round_size: Connected solves in the round that just ended.
        history_size: Connected solves preceding the round.

    Returns:
        The previous report passed to the reporter, 'not-called'
        when no report is rendered.

    """
    stack_done = analysable_solves(round_size)
    history = analysable_solves(history_size)

    with mock.patch(
            'term_timer.scripts.commands.timer.SolvesDoctorAggregator',
    ) as aggregator_cls, mock.patch(
            'term_timer.scripts.commands.timer.DoctorReporter',
    ) as reporter_cls, mock.patch(
            'term_timer.scripts.commands.timer.console',
    ):
        aggregator_cls.return_value.results = {
            'total': round_size, 'findings': [],
        }
        print_session_doctor('cfop', stack_done, history)

        report = reporter_cls.return_value.report
        if not report.called:
            return 'not-called'
        return report.call_args.args[0]


class TestPrintSessionDoctor(unittest.TestCase):
    """Baseline selection of the session-end doctor report."""

    def test_no_report_below_three_solves(self) -> None:
        """A round of two connected solves renders nothing."""
        self.assertEqual(report_previous(2, 50), 'not-called')

    def test_baseline_skipped_when_history_too_thin(self) -> None:
        """Fewer than the minimum prior solves disables the trend."""
        previous = report_previous(3, DOCTOR_SESSION_BASELINE_MIN - 1)
        self.assertIsNone(previous)

    def test_baseline_used_at_minimum_history(self) -> None:
        """Exactly the minimum prior solves enables the trend."""
        previous = report_previous(3, DOCTOR_SESSION_BASELINE_MIN)
        self.assertIsNotNone(previous)

    def test_small_round_contrasts_against_stable_floor(self) -> None:
        """A short round still compares against a fuller baseline."""
        previous = report_previous(3, 40)
        self.assertIsNotNone(previous)

    def test_large_round_uses_available_history(self) -> None:
        """A round beyond the floor trends on the history it has."""
        previous = report_previous(20, 15)
        self.assertIsNotNone(previous)

    def test_large_round_skipped_when_history_too_thin(self) -> None:
        """A large round with too few prior solves shows no trend."""
        previous = report_previous(20, DOCTOR_SESSION_BASELINE_MIN - 1)
        self.assertIsNone(previous)
