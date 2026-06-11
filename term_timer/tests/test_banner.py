"""Tests for banner."""
import re
import unittest

from term_timer import __version__
from term_timer.banner import AFTERNOON_RAMP
from term_timer.banner import EVENING_RAMP
from term_timer.banner import MORNING_RAMP
from term_timer.banner import NIGHT_RAMP
from term_timer.banner import RESET
from term_timer.banner import colorize
from term_timer.banner import get_banner
from term_timer.banner import palette_for_hour

ANSI_REGEX = re.compile(r'\033\[[0-9;]*m')


def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape sequences from text.

    Args:
        text: Text containing ANSI escape sequences.

    Returns:
        Text without ANSI escape sequences.

    """
    return ANSI_REGEX.sub('', text)


class PaletteForHourTestCase(unittest.TestCase):
    """Tests for the palette_for_hour function."""

    def test_night_hours(self) -> None:
        """Test night palette from 22h to 6h."""
        for hour in (22, 23, 0, 3, 5):
            self.assertEqual(
                palette_for_hour(hour), NIGHT_RAMP,
                f'hour { hour } should be night',
            )

    def test_morning_hours(self) -> None:
        """Test morning palette from 6h to 12h."""
        for hour in (6, 9, 11):
            self.assertEqual(
                palette_for_hour(hour), MORNING_RAMP,
                f'hour { hour } should be morning',
            )

    def test_afternoon_hours(self) -> None:
        """Test afternoon palette from 12h to 18h."""
        for hour in (12, 15, 17):
            self.assertEqual(
                palette_for_hour(hour), AFTERNOON_RAMP,
                f'hour { hour } should be afternoon',
            )

    def test_evening_hours(self) -> None:
        """Test evening palette from 18h to 22h."""
        for hour in (18, 20, 21):
            self.assertEqual(
                palette_for_hour(hour), EVENING_RAMP,
                f'hour { hour } should be evening',
            )


class ColorizeTestCase(unittest.TestCase):
    """Tests for the colorize function."""

    def test_first_char_uses_first_ramp_color(self) -> None:
        """Test first character gets the first ramp color."""
        ramp = (100, 200)
        result = colorize(['AB'], ramp)
        self.assertTrue(result.startswith('\033[38;5;100mA'))

    def test_last_column_uses_last_ramp_color(self) -> None:
        """Test last column gets the last ramp color."""
        ramp = (100, 200)
        result = colorize(['ABCD'], ramp)
        self.assertIn('\033[38;5;200mD', result)

    def test_spaces_are_not_colorized(self) -> None:
        """Test spaces receive no color code."""
        result = colorize(['A B'], (100,))
        self.assertEqual(result.count('\033[38;5;100m'), 2)

    def test_each_line_is_reset(self) -> None:
        """Test every line ends with a reset code."""
        result = colorize(['AB', 'CD'], (100, 200))
        lines = result.split('\n')
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertTrue(line.endswith(RESET))

    def test_diagonal_slope_shifts_colors_down_rows(self) -> None:
        """Test the gradient shifts on each row."""
        ramp = (100, 200)
        result = colorize(['AAAAAAAA', 'BBBBBBBB'], ramp)
        first, second = result.split('\n')
        self.assertIn('\033[38;5;100mB', second)
        self.assertIn('\033[38;5;200mB', second)
        self.assertLess(
            second.count('\033[38;5;100m'),
            first.count('\033[38;5;100m'),
        )


class GetBannerTestCase(unittest.TestCase):
    """Tests for the get_banner function."""

    def test_contains_version(self) -> None:
        """Test banner displays the package version."""
        self.assertIn(
            f'v{ __version__ }',
            strip_ansi(get_banner(hour=12)),
        )

    def test_mode_is_displayed_uppercase(self) -> None:
        """Test mode label is displayed in uppercase brackets."""
        self.assertIn(
            '[TRAINING]',
            strip_ansi(get_banner(mode='training', hour=12)),
        )

    def test_without_mode_no_label(self) -> None:
        """Test banner has no bracketed label without mode."""
        self.assertNotIn('[', strip_ansi(get_banner(hour=12)))

    def test_ends_with_rule_line(self) -> None:
        """Test banner ends with a horizontal rule."""
        last_line = get_banner(hour=12).split('\n')[-1]
        self.assertIn('═', last_line)

    def test_logo_has_five_lines_plus_rule(self) -> None:
        """Test banner is five logo lines plus the rule."""
        self.assertEqual(len(get_banner(hour=12).split('\n')), 6)

    def test_palette_changes_with_hour(self) -> None:
        """Test different hours produce different colors."""
        self.assertNotEqual(get_banner(hour=2), get_banner(hour=14))

    def test_default_hour_uses_current_time(self) -> None:
        """Test banner builds without an explicit hour."""
        banner = get_banner()
        self.assertIn(f'v{ __version__ }', strip_ansi(banner))


if __name__ == '__main__':
    unittest.main()
