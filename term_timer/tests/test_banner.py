"""Tests for banner."""
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock

from rich.color import Color

from term_timer import __version__
from term_timer.banner import COMMIT_HASH
from term_timer.banner import CUBE_LEFT
from term_timer.banner import CUBE_TILES
from term_timer.banner import CUBE_TOP
from term_timer.banner import FRIEZE
from term_timer.banner import FRIEZE_WINDOW
from term_timer.banner import LOGO_TILES
from term_timer.banner import LOGO_WIDTH
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
from term_timer.banner import frieze_color
from term_timer.banner import frieze_stops
from term_timer.banner import get_banner
from term_timer.banner import get_commit_hash
from term_timer.banner import logo_tiles
from term_timer.banner import oklab_to_rgb
from term_timer.banner import show_banner
from term_timer.banner import srgb_to_oklab
from term_timer.banner import tile_color
from term_timer.banner import window_color

# Color of the frieze at each hour, as resolved by the demo
# design/banner/frise.html
HOURLY = (
    '#2b4bff', '#4745fa', '#5a3ef5', '#6a35f0', '#8e31f8', '#b026ff',
    '#e33abc', '#fb5d82', '#ff8a3d', '#feb049', '#ffd23f', '#fee17c',
    '#feefa2', '#feec9e', '#fed96e', '#ffc400', '#fda224', '#ff7a00',
    '#fb5556', '#eb3c9c', '#c724ff', '#9650f9', '#5d5bff', '#4757f8',
)


def frieze_hex(hour: float) -> str:
    """
    Resolve the displayed color of the frieze at an hour.

    Args:
        hour: Hour of the day, fraction included.

    Returns:
        The color as a hexadecimal triplet.

    """
    red, green, blue = oklab_to_rgb(frieze_color(hour))
    return f'#{ red:02x}{ green:02x}{ blue:02x}'


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

    def test_frieze_colors_survive_the_round_trip(self) -> None:
        """Test every frieze color converts to OKLab and back."""
        for _, color in FRIEZE:
            rgb = Color.parse(color).get_truecolor()
            self.assertEqual(oklab_to_rgb(srgb_to_oklab(rgb)), rgb, color)

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


class FriezeColorTestCase(unittest.TestCase):
    """Tests for the frieze_color and window_color functions."""

    def test_stops_are_sorted_within_the_day(self) -> None:
        """Test the stops follow each other from midnight on."""
        hours = [hour for hour, _ in FRIEZE]
        self.assertEqual(hours, sorted(set(hours)))
        self.assertGreaterEqual(hours[0], 0)
        self.assertLess(hours[-1], 24)

    def test_stops_keep_their_color(self) -> None:
        """Test the frieze passes through each of its stops."""
        for (hour, color), stop in zip(FRIEZE, frieze_stops(), strict=True):
            self.assertEqual(frieze_color(hour), stop)
            self.assertEqual(frieze_hex(hour), color)

    def test_hourly_colors(self) -> None:
        """Test the color of each hour, against the demo values."""
        for hour, color in enumerate(HOURLY):
            self.assertEqual(frieze_hex(hour), color, f'hour { hour }')

    def test_frieze_is_closed_over_midnight(self) -> None:
        """Test the last stop joins the first one across midnight."""
        self.assertEqual(frieze_color(24), frieze_color(0))
        self.assertEqual(frieze_color(-1), frieze_color(23))
        self.assertEqual(frieze_color(30.5), frieze_color(6.5))
        last = frieze_stops()[-1]
        first = frieze_stops()[0]
        self.assertEqual(
            frieze_color(23),
            tuple(
                start + (end - start) * .5
                for start, end in zip(last, first, strict=True)
            ),
        )

    def test_frieze_is_continuous(self) -> None:
        """Test no minute of the day jumps to another color."""
        for minute in range(24 * 60):
            before = frieze_color(minute / 60)
            after = frieze_color((minute + 1) / 60)
            step = max(
                abs(start - end)
                for start, end in zip(before, after, strict=True)
            )
            self.assertLess(step, .01, f'minute { minute }')

    def test_lightness_and_chroma(self) -> None:
        """Test the lightness is added and the chroma multiplied."""
        lightness, axis_a, axis_b = frieze_color(9.25)
        self.assertEqual(
            frieze_color(9.25, -.1, 2),
            (lightness - .1, axis_a * 2, axis_b * 2),
        )

    def test_window_is_centered_on_the_hour(self) -> None:
        """Test a banner walks the frieze around its hour."""
        half = FRIEZE_WINDOW / 2
        self.assertEqual(window_color(18.5, .5), frieze_color(18.5))
        self.assertEqual(window_color(18.5, 0), frieze_color(18.5 - half))
        self.assertEqual(window_color(18.5, 1), frieze_color(18.5 + half))

    def test_window_crosses_midnight(self) -> None:
        """Test the window of a late banner goes on after midnight."""
        half = FRIEZE_WINDOW / 2
        self.assertEqual(window_color(23, 1), frieze_color(23 + half - 24))
        self.assertEqual(window_color(1, 0), frieze_color(1 - half + 24))


class TileColorTestCase(unittest.TestCase):
    """Tests for the tile_color function, against the demo values."""

    def test_empty_tile_has_no_color(self) -> None:
        """Test an empty tile is not colored."""
        self.assertEqual(LOGO_TILES[0][9], TILE_EMPTY)
        self.assertIsNone(tile_color(LOGO_TILES, 9, 0, 18.5))

    def test_first_tile_opens_the_window(self) -> None:
        """Test the top left tile takes the start of the window."""
        expected = {
            0: (124, 88, 249),
            6.5: (142, 49, 248),
            12: (254, 193, 75),
            18.5: (253, 162, 36),
            23.75: (137, 84, 249),
        }
        for hour, rgb in expected.items():
            self.assertEqual(tile_color(LOGO_TILES, 0, 0, hour), rgb)
            self.assertEqual(
                rgb,
                oklab_to_rgb(frieze_color(hour - FRIEZE_WINDOW / 2)),
            )

    def test_gradient_runs_along_the_diagonal(self) -> None:
        """Test two tiles of the same diagonal share their color."""
        self.assertEqual(LOGO_TILES[0][4], TILE_INK)
        self.assertEqual(LOGO_TILES[1][3], TILE_INK)
        self.assertEqual(
            tile_color(LOGO_TILES, 4, 0, 18.5),
            tile_color(LOGO_TILES, 3, 1, 18.5),
        )
        self.assertNotEqual(
            tile_color(LOGO_TILES, 4, 0, 18.5),
            tile_color(LOGO_TILES, 5, 1, 18.5),
        )

    def test_ink_colors(self) -> None:
        """Test a tile deep in the grid, at several hours."""
        self.assertEqual(LOGO_TILES[10][70], TILE_INK)
        expected = {
            0: (83, 65, 247),
            6.5: (252, 143, 70),
            12: (254, 225, 131),
            18.5: (195, 41, 255),
            23.75: (78, 67, 248),
        }
        for hour, rgb in expected.items():
            self.assertEqual(tile_color(LOGO_TILES, 70, 10, hour), rgb)

    def test_shadow_colors(self) -> None:
        """Test a shadow tile is a dark tint of its place in the frieze."""
        self.assertEqual(LOGO_TILES[1][9], TILE_SHADOW)
        expected = {
            0: (42, 45, 115),
            6.5: (72, 28, 112),
            12: (69, 54, 1),
            18.5: (86, 43, 0),
            23.75: (49, 43, 114),
        }
        for hour, rgb in expected.items():
            self.assertEqual(tile_color(LOGO_TILES, 9, 1, hour), rgb)

    def test_sticker_colors(self) -> None:
        """Test the nine stickers of the cube at half past six pm."""
        expected = (
            ((191, 87, 250), (185, 90, 249), (178, 93, 249)),
            ((179, 65, 249), (172, 69, 249), (164, 73, 249)),
            ((161, 44, 241), (154, 50, 241), (147, 55, 241)),
        )
        for row, colors in enumerate(expected):
            for column, rgb in enumerate(colors):
                self.assertEqual(
                    tile_color(
                        LOGO_TILES,
                        CUBE_LEFT + column * STICKER_PITCH,
                        CUBE_TOP + row * STICKER_PITCH,
                        18.5,
                    ),
                    rgb,
                )

    def test_sticker_has_a_single_color(self) -> None:
        """Test the four tiles of a sticker share their color."""
        colors = set()
        for y in range(CUBE_TOP, CUBE_TOP + STICKER_SIZE):
            for x in range(CUBE_LEFT, CUBE_LEFT + STICKER_SIZE):
                self.assertEqual(LOGO_TILES[y][x], TILE_STICKER)
                colors.add(tile_color(LOGO_TILES, x, y, 2))
        self.assertEqual(len(colors), 1)

    def test_word_alone_spreads_the_whole_window(self) -> None:
        """Test the window spans the grid it colors, cube or not."""
        self.assertEqual(
            tile_color(WORD_TILES, 0, 0, 18.5), (253, 162, 36),
        )
        self.assertEqual(
            tile_color(WORD_TILES, 70, 10, 18.5), (171, 69, 249),
        )
        self.assertNotEqual(
            tile_color(WORD_TILES, 70, 10, 18.5),
            tile_color(LOGO_TILES, 70, 10, 18.5),
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
            self, mode: str | None = None, hour: float = 18.5,
            width: int = LOGO_WIDTH,
    ) -> list[str]:
        """
        Build a banner and split its text into lines.

        Args:
            mode: Optional mode label.
            hour: Hour of the frieze, fraction included.
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
        """Test version and mode colors, against the demo values."""
        banner = get_banner(mode='training', hour=18.5)
        if banner is None:
            self.fail('no banner for this width')
        footer = banner.split('\n')[-1]
        version, badge = (span.style for span in footer.spans[-2:])
        self.assertEqual(
            tuple(Color.parse(str(version)).get_truecolor()),
            (141, 52, 247),
        )
        self.assertEqual(str(badge), '#000000 on #f2227b')
        self.assertEqual(str(footer.spans[0].style), '#b4710e')

    def test_colors_change_with_the_hour(self) -> None:
        """Test different hours produce different colors."""
        night = get_banner(hour=2)
        afternoon = get_banner(hour=14)
        if night is None or afternoon is None:
            self.fail('no banner for this width')
        self.assertEqual(night.plain, afternoon.plain)
        self.assertNotEqual(night.spans, afternoon.spans)

    def test_colors_change_within_the_hour(self) -> None:
        """Test half an hour is enough to color a banner differently."""
        early = get_banner(hour=14)
        late = get_banner(hour=14.5)
        if early is None or late is None:
            self.fail('no banner for this width')
        self.assertNotEqual(early.spans, late.spans)

    def test_default_hour_uses_current_time(self) -> None:
        """Test banner follows the clock to the minute by default."""
        moment = datetime(2026, 11, 11, 18, 30, tzinfo=UTC).replace(
            tzinfo=None,
        ).astimezone()
        with mock.patch('term_timer.banner.datetime') as clock:
            clock.now.return_value = moment
            banner = get_banner()
        expected = get_banner(hour=18.5)
        if banner is None or expected is None:
            self.fail('no banner for this width')
        self.assertEqual(banner.spans, expected.spans)


class ShowBannerTestCase(unittest.TestCase):
    """Tests for the show_banner function."""

    def test_banner_is_printed(self) -> None:
        """Test the banner is printed at the width of the console."""
        with mock.patch('term_timer.banner.console') as console:
            console.width = 80
            show_banner(mode='training', hour=18.5)
        console.print.assert_called_once()
        banner = console.print.call_args.args[0]
        self.assertEqual(len(banner.plain.split('\n')[0]), WORD_WIDTH)

    def test_nothing_is_printed_on_a_narrow_console(self) -> None:
        """Test a console too narrow for the word stays empty."""
        with mock.patch('term_timer.banner.console') as console:
            console.width = WORD_WIDTH - 1
            show_banner(mode='training', hour=18.5)
        self.assertEqual(console.print.call_count, 0)
