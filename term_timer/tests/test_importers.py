"""Tests for importers."""
import unittest

from term_timer.importers import Importer


class TestImporterTimeToNs(unittest.TestCase):
    """Tests for the parsing of the csTimer CSV times."""

    def test_centiseconds(self) -> None:
        """Two decimals are centiseconds."""
        self.assertEqual(Importer.time_to_ns('12.29'), 12_290_000_000)

    def test_milliseconds(self) -> None:
        """Three decimals are milliseconds, not extra centiseconds."""
        self.assertEqual(Importer.time_to_ns('12.345'), 12_345_000_000)

    def test_tenths(self) -> None:
        """A single decimal is tenths of a second."""
        self.assertEqual(Importer.time_to_ns('12.5'), 12_500_000_000)

    def test_minutes_exact(self) -> None:
        """Minutes are added without any float truncation."""
        self.assertEqual(Importer.time_to_ns('1:05.07'), 65_070_000_000)

    def test_hours(self) -> None:
        """A time of an hour or more is parsed."""
        self.assertEqual(
            Importer.time_to_ns('1:02:03.45'), 3_723_450_000_000,
        )

    def test_no_fraction(self) -> None:
        """A time without decimals is whole seconds."""
        self.assertEqual(Importer.time_to_ns('12'), 12_000_000_000)

    def test_cstimer_csv(self) -> None:
        """A csTimer CSV line keeps its exact time and penalty."""
        data = [
            'No.;Time;Comment;Scramble;Date;P.1',
            "1;12.345+;;R U R' U';2025-01-02 03:04:05;12.345",
        ]

        solves = Importer().cstimer_csv(data)

        self.assertEqual(len(solves), 1)
        self.assertEqual(solves[0]['time'], 12_345_000_000)
        self.assertEqual(solves[0]['flag'], '+2')
