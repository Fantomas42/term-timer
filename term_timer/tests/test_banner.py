"""Tests for banner."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rich.color import Color

from term_timer import __version__
from term_timer.banner import AFTERNOON_RAMP
from term_timer.banner import COMMIT_HASH
from term_timer.banner import CUBE_LEFT
from term_timer.banner import CUBE_TILES
from term_timer.banner import CUBE_TOP
from term_timer.banner import EVENING_RAMP
from term_timer.banner import LOGO_TILES
from term_timer.banner import LOGO_WIDTH
from term_timer.banner import MORNING_RAMP
from term_timer.banner import NIGHT_RAMP
from term_timer.banner import NOON_RAMP
from term_timer.banner import RULE
from term_timer.banner import STICKER_PITCH
from term_timer.banner import STICKER_SIZE
from term_timer.banner import TERM_TILES
from term_timer.banner import TILE_EMPTY
from term_timer.banner import TILE_INK
from term_timer.banner import TILE_SHADOW
from term_timer.banner import TILE_STICKER
from term_timer.banner import TIMER_TILES
from term_timer.banner import WORD_TILES
from term_timer.banner import WORD_WIDTH
from term_timer.banner import get_banner
from term_timer.banner import get_commit_hash
from term_timer.banner import logo_tiles
from term_timer.banner import oklab_to_rgb
from term_timer.banner import palette_for_hour
from term_timer.banner import ramp_color
from term_timer.banner import ramp_stops
from term_timer.banner import show_banner
from term_timer.banner import srgb_to_oklab
from term_timer.banner import tile_color

RAMPS = (
    NIGHT_RAMP, MORNING_RAMP, NOON_RAMP, AFTERNOON_RAMP, EVENING_RAMP,
)


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
        for hour in (6, 9, 10):
            self.assertEqual(
                palette_for_hour(hour), MORNING_RAMP,
                f'hour { hour } should be morning',
            )

    def test_noon_hours(self) -> None:
        """Test noon palette from 11h to 14h."""
        for hour in (11, 12, 13):
            self.assertEqual(
                palette_for_hour(hour), NOON_RAMP,
                f'hour { hour } should be noon',
            )

    def test_afternoon_hours(self) -> None:
        """Test afternoon palette from 14h to 18h."""
        for hour in (14, 15, 17):
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


def count_tiles(rows: tuple[str, ...], tile: str) -> int:
    """
    Count the tiles of a kind in a grid.

    Args:
        rows: Rows of the tile grid.
        tile: Kind of tile to count.

    Returns:
        Number of tiles of that kind.

    """
    return sum(row.count(tile) for row in rows)


class LogoTilesTestCase(unittest.TestCase):
    """Tests for the frozen tile grid and its width fallback."""

    def test_grid_dimensions(self) -> None:
        """Test the grid is 86 tiles wide and 14 tiles high."""
        self.assertEqual(LOGO_WIDTH, 86)
        self.assertEqual(len(LOGO_TILES), 14)
        for row in LOGO_TILES:
            self.assertEqual(len(row), LOGO_WIDTH)

    def test_grid_pairs_into_seven_lines(self) -> None:
        """Test the rows pair two by two into half-block lines."""
        self.assertEqual(len(LOGO_TILES) % 2, 0)
        self.assertEqual(len(LOGO_TILES) // 2, 7)

    def test_parts_share_the_same_height(self) -> None:
        """Test the three parts of the grid are equally high."""
        for part in (TERM_TILES, TIMER_TILES, CUBE_TILES):
            self.assertEqual(len(part), len(LOGO_TILES))

    def test_only_known_tiles(self) -> None:
        """Test the grid holds nothing but the four tile kinds."""
        kinds = {TILE_EMPTY, TILE_INK, TILE_SHADOW, TILE_STICKER}
        for row in LOGO_TILES:
            self.assertLessEqual(set(row), kinds)

    def test_tile_counts(self) -> None:
        """Test the tile counts match the mockup."""
        self.assertEqual(count_tiles(LOGO_TILES, TILE_INK), 450)
        self.assertEqual(count_tiles(LOGO_TILES, TILE_SHADOW), 195)
        self.assertEqual(count_tiles(LOGO_TILES, TILE_STICKER), 36)

    def test_words_start_on_a_capital_bar(self) -> None:
        """Test both words open with the nine tiles of a T bar."""
        self.assertTrue(TERM_TILES[0].startswith(TILE_INK * 9))
        self.assertTrue(TIMER_TILES[0].startswith(TILE_INK * 9))
        self.assertEqual(LOGO_TILES[0].count(TILE_INK), 18)

    def test_shadow_is_cast_down_right(self) -> None:
        """Test every shadow tile lies down right of a solid tile."""
        solid = {TILE_INK, TILE_STICKER}
        for rows in (LOGO_TILES, WORD_TILES):
            for y, row in enumerate(rows):
                for x, tile in enumerate(row):
                    if tile == TILE_SHADOW:
                        self.assertIn(rows[y - 1][x - 1], solid)
                    elif tile in solid and x + 1 < len(row):
                        self.assertNotEqual(
                            rows[y + 1][x + 1], TILE_EMPTY,
                        )

    def test_cube_is_three_by_three_stickers(self) -> None:
        """Test the cube is nine stickers of two by two tiles."""
        sticker_rows = [
            row for row in CUBE_TILES if TILE_STICKER in row
        ]
        self.assertEqual(len(sticker_rows), 6)
        for row in sticker_rows:
            self.assertEqual(
                row.replace(TILE_SHADOW, TILE_EMPTY), '.oo.oo.oo.',
            )

    def test_full_grid_from_its_width(self) -> None:
        """Test a terminal of 86 columns or more gets the cube."""
        for width in (LOGO_WIDTH, LOGO_WIDTH + 1, 200):
            self.assertEqual(logo_tiles(width), LOGO_TILES)

    def test_word_alone_under_the_full_width(self) -> None:
        """Test a narrower terminal loses the cube, not the word."""
        self.assertEqual(WORD_WIDTH, 76)
        for width in (WORD_WIDTH, 80, LOGO_WIDTH - 1):
            self.assertEqual(logo_tiles(width), WORD_TILES)

    def test_word_grid_has_no_cube(self) -> None:
        """Test the word grid keeps the letters and drops the cube."""
        self.assertEqual(len(WORD_TILES), len(LOGO_TILES))
        for row in WORD_TILES:
            self.assertEqual(len(row), WORD_WIDTH)
        self.assertEqual(count_tiles(WORD_TILES, TILE_STICKER), 0)
        self.assertEqual(count_tiles(WORD_TILES, TILE_INK), 450)
        self.assertEqual(count_tiles(WORD_TILES, TILE_SHADOW), 168)

    def test_no_grid_under_the_word_width(self) -> None:
        """Test a terminal too narrow for the word gets nothing."""
        for width in (WORD_WIDTH - 1, 40, 0):
            self.assertIsNone(logo_tiles(width))


class OklabTestCase(unittest.TestCase):
    """Tests for the OKLab conversions."""

    def test_ramp_colors_survive_the_round_trip(self) -> None:
        """Test every ramp color converts to OKLab and back."""
        for ramp in RAMPS:
            for index in ramp:
                rgb = Color.from_ansi(index).get_truecolor()
                self.assertEqual(
                    oklab_to_rgb(srgb_to_oklab(rgb)), rgb,
                    f'color { index }',
                )

    def test_white_and_black(self) -> None:
        """Test the ends of the lightness axis."""
        self.assertEqual(oklab_to_rgb((1, 0, 0)), (255, 255, 255))
        self.assertEqual(oklab_to_rgb((0, 0, 0)), (0, 0, 0))

    def test_lightness_is_clamped(self) -> None:
        """Test a lightness outside 0-1 is brought back inside."""
        self.assertEqual(oklab_to_rgb((1.5, 0, 0)), (255, 255, 255))
        self.assertEqual(oklab_to_rgb((-.5, 0, 0)), (0, 0, 0))

    def test_out_of_gamut_chroma_is_reduced(self) -> None:
        """Test a color too saturated for sRGB keeps its lightness."""
        rgb = oklab_to_rgb((.7, .4, 0))
        for component in rgb:
            self.assertGreaterEqual(component, 0)
            self.assertLessEqual(component, 255)
        self.assertAlmostEqual(srgb_to_oklab(rgb)[0], .7, places=2)


class RampColorTestCase(unittest.TestCase):
    """Tests for the ramp_color function."""

    def test_ends_are_the_ramp_ends(self) -> None:
        """Test the gradient starts and ends on the ramp colors."""
        for ramp in RAMPS:
            stops = ramp_stops(ramp)
            self.assertEqual(ramp_color(ramp, 0), stops[0])
            self.assertEqual(ramp_color(ramp, 1), stops[-1])

    def test_position_is_clamped(self) -> None:
        """Test a position outside the gradient takes its ends."""
        self.assertEqual(
            ramp_color(NIGHT_RAMP, -1), ramp_color(NIGHT_RAMP, 0),
        )
        self.assertEqual(
            ramp_color(NIGHT_RAMP, 2), ramp_color(NIGHT_RAMP, 1),
        )

    def test_lightness_and_chroma(self) -> None:
        """Test the lightness is added and the chroma multiplied."""
        lightness, axis_a, axis_b = ramp_color(EVENING_RAMP, .5)
        self.assertEqual(
            ramp_color(EVENING_RAMP, .5, -.1, 2),
            (lightness - .1, axis_a * 2, axis_b * 2),
        )


class TileColorTestCase(unittest.TestCase):
    """Tests for the tile_color function, against the mockup values."""

    def test_empty_tile_has_no_color(self) -> None:
        """Test an empty tile is not colored."""
        self.assertEqual(LOGO_TILES[0][9], TILE_EMPTY)
        self.assertIsNone(tile_color(LOGO_TILES, 9, 0, EVENING_RAMP))

    def test_first_tile_takes_the_first_ramp_color(self) -> None:
        """Test the gradient starts on the top left tile."""
        expected = {
            NIGHT_RAMP: (0, 95, 255),
            MORNING_RAMP: (255, 0, 175),
            NOON_RAMP: (255, 255, 255),
            AFTERNOON_RAMP: (255, 255, 0),
            EVENING_RAMP: (0, 255, 255),
        }
        for ramp, rgb in expected.items():
            self.assertEqual(tile_color(LOGO_TILES, 0, 0, ramp), rgb)

    def test_gradient_runs_along_the_diagonal(self) -> None:
        """Test two tiles of the same diagonal share their color."""
        self.assertEqual(LOGO_TILES[0][4], TILE_INK)
        self.assertEqual(LOGO_TILES[1][3], TILE_INK)
        self.assertEqual(
            tile_color(LOGO_TILES, 4, 0, EVENING_RAMP),
            tile_color(LOGO_TILES, 3, 1, EVENING_RAMP),
        )
        self.assertNotEqual(
            tile_color(LOGO_TILES, 4, 0, EVENING_RAMP),
            tile_color(LOGO_TILES, 5, 1, EVENING_RAMP),
        )

    def test_shadow_colors(self) -> None:
        """Test a shadow tile is a dark tint of its place in the ramp."""
        self.assertEqual(LOGO_TILES[1][9], TILE_SHADOW)
        expected = {
            NIGHT_RAMP: (34, 48, 116),
            MORNING_RAMP: (97, 20, 64),
            NOON_RAMP: (57, 57, 46),
            AFTERNOON_RAMP: (64, 56, 6),
            EVENING_RAMP: (2, 64, 73),
        }
        for ramp, rgb in expected.items():
            self.assertEqual(tile_color(LOGO_TILES, 9, 1, ramp), rgb)

    def test_sticker_colors(self) -> None:
        """Test the nine stickers of the cube in the evening."""
        expected = (
            ((216, 120, 253), (224, 116, 253), (232, 108, 253)),
            ((221, 88, 255), (230, 77, 255), (238, 63, 255)),
            ((216, 61, 241), (224, 43, 241), (232, 8, 241)),
        )
        for row, colors in enumerate(expected):
            for column, rgb in enumerate(colors):
                self.assertEqual(
                    tile_color(
                        LOGO_TILES,
                        CUBE_LEFT + column * STICKER_PITCH,
                        CUBE_TOP + row * STICKER_PITCH,
                        EVENING_RAMP,
                    ),
                    rgb,
                )

    def test_sticker_has_a_single_color(self) -> None:
        """Test the four tiles of a sticker share their color."""
        colors = set()
        for y in range(CUBE_TOP, CUBE_TOP + STICKER_SIZE):
            for x in range(CUBE_LEFT, CUBE_LEFT + STICKER_SIZE):
                self.assertEqual(LOGO_TILES[y][x], TILE_STICKER)
                colors.add(tile_color(LOGO_TILES, x, y, NIGHT_RAMP))
        self.assertEqual(len(colors), 1)

    def test_word_alone_spreads_the_whole_ramp(self) -> None:
        """Test the gradient spans the grid it colors, cube or not."""
        self.assertEqual(
            tile_color(WORD_TILES, 0, 0, EVENING_RAMP), (0, 255, 255),
        )
        self.assertNotEqual(
            tile_color(WORD_TILES, 70, 10, EVENING_RAMP),
            tile_color(LOGO_TILES, 70, 10, EVENING_RAMP),
        )


class GetCommitHashTestCase(unittest.TestCase):
    """Tests for the get_commit_hash function."""

    def setUp(self) -> None:
        """Create a fake .git directory for each test."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.git_dir = Path(self.tmp.name)
        patcher = mock.patch('term_timer.banner.GIT_DIR', self.git_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name: str, content: str) -> None:
        """Write a file inside the fake .git directory."""
        path = self.git_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_loose_ref(self) -> None:
        """Test the hash is read from a loose ref."""
        self.write('HEAD', 'ref: refs/heads/develop\n')
        self.write('refs/heads/develop', 'abcdef1234567890\n')
        self.assertEqual(get_commit_hash(), 'abcdef1')

    def test_packed_ref(self) -> None:
        """Test the hash is read from packed-refs when loose is absent."""
        self.write('HEAD', 'ref: refs/heads/develop\n')
        self.write(
            'packed-refs',
            '# pack-refs with: peeled fully-peeled sorted\n'
            'fedcba9876543210 refs/heads/develop\n'
            '^0123456789abcdef\n',
        )
        self.assertEqual(get_commit_hash(), 'fedcba9')

    def test_detached_head(self) -> None:
        """Test the hash is read directly from a detached HEAD."""
        self.write('HEAD', '1234567890abcdef\n')
        self.assertEqual(get_commit_hash(), '1234567')

    def test_no_git_directory(self) -> None:
        """Test None is returned when HEAD is missing."""
        self.assertIsNone(get_commit_hash())

    def test_ref_not_found(self) -> None:
        """Test None is returned when the ref resolves to nothing."""
        self.write('HEAD', 'ref: refs/heads/develop\n')
        self.write('packed-refs', 'fedcba9876543210 refs/heads/master\n')
        self.assertIsNone(get_commit_hash())

    def test_empty_head(self) -> None:
        """Test None is returned for an empty HEAD file."""
        self.write('HEAD', '\n')
        self.assertIsNone(get_commit_hash())


class GetBannerTestCase(unittest.TestCase):
    """Tests for the get_banner function."""

    def banner_lines(
            self, mode: str | None = None, hour: int = 20,
            width: int = LOGO_WIDTH,
    ) -> list[str]:
        """
        Build a banner and split its text into lines.

        Args:
            mode: Optional mode label.
            hour: Hour used to pick the palette.
            width: Width of the terminal in columns.

        Returns:
            The lines of the banner, without their styles.

        """
        banner = get_banner(mode=mode, hour=hour, width=width)
        if banner is None:
            self.fail('no banner for this width')
        return banner.plain.split('\n')

    def test_contains_version(self) -> None:
        """Test banner displays the version or commit hash."""
        self.assertIn(
            f'v{ COMMIT_HASH or __version__ }', self.banner_lines()[-1],
        )

    def test_mode_is_displayed_uppercase(self) -> None:
        """Test mode label closes the footer in uppercase."""
        self.assertTrue(
            self.banner_lines(mode='training')[-1].endswith(' TRAINING '),
        )

    def test_without_mode_footer_ends_on_version(self) -> None:
        """Test banner ends on the version without mode."""
        self.assertTrue(
            self.banner_lines()[-1].endswith(
                f' v{ COMMIT_HASH or __version__ }',
            ),
        )

    def test_ends_with_rule_line(self) -> None:
        """Test banner ends with a horizontal rule."""
        self.assertTrue(self.banner_lines()[-1].startswith(RULE * 40))

    def test_logo_has_seven_lines_plus_rule(self) -> None:
        """Test banner is seven logo lines plus the rule."""
        self.assertEqual(len(self.banner_lines()), 8)

    def test_fits_in_the_logo_width(self) -> None:
        """Test no line is wider than the logo."""
        lines = self.banner_lines(mode='training')
        for line in lines[:-1]:
            self.assertEqual(len(line), LOGO_WIDTH)
        self.assertEqual(len(lines[-1]), LOGO_WIDTH - 1)

    def test_narrow_terminal_loses_the_cube(self) -> None:
        """Test banner shrinks to the word on a narrow terminal."""
        lines = self.banner_lines(mode='training', width=80)
        self.assertEqual(len(lines), 8)
        for line in lines[:-1]:
            self.assertEqual(len(line), WORD_WIDTH)
        self.assertEqual(len(lines[-1]), WORD_WIDTH - 1)

    def test_no_banner_under_the_word_width(self) -> None:
        """Test there is no banner when the word does not fit."""
        self.assertIsNone(get_banner(hour=12, width=WORD_WIDTH - 1))

    def test_footer_colors(self) -> None:
        """Test version and mode colors, against the mockup values."""
        banner = get_banner(mode='training', hour=20)
        if banner is None:
            self.fail('no banner for this width')
        footer = banner.split('\n')[-1]
        version, badge = (span.style for span in footer.spans[-2:])
        self.assertEqual(
            tuple(Color.parse(str(version)).get_truecolor()),
            (233, 28, 233),
        )
        self.assertEqual(str(badge), '#000000 on #7d5cfe')
        self.assertEqual(str(footer.spans[0].style), '#02bebe')

    def test_palette_changes_with_hour(self) -> None:
        """Test different hours produce different colors."""
        night = get_banner(hour=2)
        afternoon = get_banner(hour=14)
        if night is None or afternoon is None:
            self.fail('no banner for this width')
        self.assertEqual(night.plain, afternoon.plain)
        self.assertNotEqual(night.spans, afternoon.spans)

    def test_default_hour_uses_current_time(self) -> None:
        """Test banner builds without an explicit hour."""
        banner = get_banner()
        if banner is None:
            self.fail('no banner for this width')
        self.assertIn(f'v{ COMMIT_HASH or __version__ }', banner.plain)


class ShowBannerTestCase(unittest.TestCase):
    """Tests for the show_banner function."""

    def test_banner_is_printed(self) -> None:
        """Test the banner is printed at the width of the console."""
        with mock.patch('term_timer.banner.console') as console:
            console.width = 80
            show_banner(mode='training', hour=20)
        console.print.assert_called_once()
        banner = console.print.call_args.args[0]
        self.assertEqual(len(banner.plain.split('\n')[0]), WORD_WIDTH)

    def test_nothing_is_printed_on_a_narrow_console(self) -> None:
        """Test a console too narrow for the word stays empty."""
        with mock.patch('term_timer.banner.console') as console:
            console.width = WORD_WIDTH - 1
            show_banner(mode='training', hour=20)
        self.assertEqual(console.print.call_count, 0)
