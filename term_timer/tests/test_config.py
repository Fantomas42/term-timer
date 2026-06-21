"""Tests for config helpers."""
import unittest

from term_timer.config import parse_graph_series


class TestParseGraphSeries(unittest.TestCase):
    """Tests for parse_graph_series."""

    def test_default_tokens(self) -> None:
        """All four kinds of valid tokens are parsed."""
        self.assertEqual(
            parse_graph_series(['ao5', 'ao12', 'ao100', 'ao1000']),
            [('ao', 5), ('ao', 12), ('ao', 100), ('ao', 1000)],
        )

    def test_all_kinds(self) -> None:
        """Every supported kind is recognised."""
        self.assertEqual(
            parse_graph_series(['mo3', 'ao5', 'mb3', 'mw10']),
            [('mo', 3), ('ao', 5), ('mb', 3), ('mw', 10)],
        )

    def test_order_preserved(self) -> None:
        """The user-provided order is kept as-is."""
        self.assertEqual(
            parse_graph_series(['ao1000', 'ao5', 'ao100', 'ao12']),
            [('ao', 1000), ('ao', 5), ('ao', 100), ('ao', 12)],
        )

    def test_invalid_tokens_ignored(self) -> None:
        """Unrecognised tokens are silently dropped."""
        self.assertEqual(
            parse_graph_series(['ao5', 'foo', 'po12', 'ao', '5', 'ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_deduplicate_first_occurrence(self) -> None:
        """Duplicates are dropped on their first occurrence."""
        self.assertEqual(
            parse_graph_series(['ao5', 'ao12', 'ao5', 'ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_case_and_whitespace_normalised(self) -> None:
        """Tokens are lowercased and stripped before matching."""
        self.assertEqual(
            parse_graph_series([' AO5 ', 'Ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_empty(self) -> None:
        """An empty list yields an empty series."""
        self.assertEqual(parse_graph_series([]), [])
