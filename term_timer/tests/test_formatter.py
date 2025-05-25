import unittest

from term_timer.constants import DNF
from term_timer.constants import SECOND
from term_timer.formatter import compute_padding
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_time


class TestFormatTime(unittest.TestCase):
    def test_format_time_with_zero(self):
        """Test that format_time returns DNF for zero value."""
        self.assertEqual(format_time(0), DNF)

    def test_format_time_with_milliseconds(self):
        """Test formatting time with milliseconds."""
        time_ns = 12345678900  # 12.345678900 seconds
        expected = '00:12.345'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_with_minutes(self):
        """Test formatting time with minutes."""
        time_ns = 65 * SECOND  # 65 seconds = 1:05
        expected = '01:05.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_with_hours(self):
        """Test formatting time with hours."""
        time_ns = 3665 * SECOND  # 3665 seconds = 01:01:05
        expected = '01:01:05.000'
        self.assertEqual(format_time(time_ns), expected)


class TestFormatDuration(unittest.TestCase):

    def test_format_duration(self):
        """Test formatting duration as seconds with decimal places."""
        duration_ns = 12345678900  # 12.345678900 seconds
        expected = '12.35'  # Rounded to 2 decimal places
        self.assertEqual(format_duration(duration_ns), expected)


class TestFormatEdge(unittest.TestCase):

    def test_format_edge(self):
        """Test formatting edge value as integer seconds."""
        edge_ns = 12

        expected = '00:12'
        self.assertEqual(format_edge(edge_ns, 605), expected)

        expected = '0:12'
        self.assertEqual(format_edge(edge_ns, 75), expected)

        expected = '12s'
        self.assertEqual(format_edge(edge_ns, 59), expected)

    def test_format_edge_minutes(self):
        """Test formatting edge value as integer seconds."""
        edge_ns = 72

        expected = '01:12'
        self.assertEqual(format_edge(edge_ns, 605), expected)

        expected = '1:12'
        self.assertEqual(format_edge(edge_ns, 75), expected)

        expected = '12s'
        self.assertEqual(format_edge(edge_ns, 59), expected)


class TestFormatDelta(unittest.TestCase):

    def test_format_delta_zero(self):
        """Test formatting delta of zero returns empty string."""
        self.assertEqual(format_delta(0), '')

    def test_format_delta_positive(self):
        """Test formatting positive delta with red color."""
        delta_ns = 1 * SECOND
        expected = '[red]+1.00[/red]'
        self.assertEqual(format_delta(delta_ns), expected)

    def test_format_delta_negative(self):
        """Test formatting negative delta with green color."""
        delta_ns = -1 * SECOND
        expected = '[green]-1.00[/green]'
        self.assertEqual(format_delta(delta_ns), expected)


class TestComputingPadding(unittest.TestCase):

    def test_compute_padding_small(self):
        """Test computing padding for small values."""
        self.assertEqual(compute_padding(5), 1)

    def test_compute_padding_medium(self):
        """Test computing padding for medium values."""
        self.assertEqual(compute_padding(15), 2)

    def test_compute_padding_large(self):
        """Test computing padding for large values."""
        self.assertEqual(compute_padding(150), 3)

    def test_compute_padding_very_large(self):
        """Test computing padding for very large values."""
        self.assertEqual(compute_padding(1500), 4)
