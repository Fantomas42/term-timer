"""Splash screen banner in tiles with a time-of-day color palette."""
import math
from datetime import UTC
from datetime import datetime
from functools import cache
from pathlib import Path

from rich.color import Color
from rich.style import Style
from rich.text import Text

from term_timer import __version__
from term_timer.interface.console import console

GIT_DIR = Path(__file__).resolve().parent.parent / '.git'
SHORT_HASH_LENGTH = 7

# Tile grid of the logo, frozen from design/banner/index.html: one tile
# is one column wide and half a line high, the rows pairing two by two
# into half-block lines
TILE_EMPTY = '.'
TILE_INK = '#'
TILE_SHADOW = '+'
TILE_STICKER = 'o'

TERM_TILES = (
    '#########...........................',
    '#########+..........................',
    '#########+..........................',
    '.++###++++..........................',
    '...###+.######..###.###..###.#####..',
    '...###+########.#######+###########.',
    '...###+###++###+####++++###+###+###+',
    '...###+########+###++...###+###+###+',
    '...###+########+###+....###+###+###+',
    '...###+###++++++###+....###+###+###+',
    '...###+########.###+....###+###+###+',
    '...###+.#######+###+....###+###+###+',
    '....+++..+++++++.+++.....+++.+++.+++',
    '....................................',
)

TIMER_TILES = (
    '#########...............................',
    '#########+..............................',
    '#########+..............................',
    '.++###++++..............................',
    '...###+###..###.#####...######..###.###.',
    '...###+###+###########.########.#######+',
    '...###+###+###+###+###+###++###+####++++',
    '...###+###+###+###+###+########+###++...',
    '...###+###+###+###+###+########+###+....',
    '...###+###+###+###+###+###++++++###+....',
    '...###+###+###+###+###+########.###+....',
    '...###+###+###+###+###+.#######+###+....',
    '....+++.+++.+++.+++.+++..+++++++.+++....',
    '........................................',
)

# Cube cursor closing the word: a face of 3x3 stickers on the baseline
CUBE_TILES = (
    '..........',
    '..........',
    '..........',
    '..........',
    '.oo.oo.oo.',
    '.oo+oo+oo+',
    '..++.++.++',
    '.oo.oo.oo.',
    '.oo+oo+oo+',
    '..++.++.++',
    '.oo.oo.oo.',
    '.oo+oo+oo+',
    '..++.++.++',
    '..........',
)

WORD_TILES = tuple(
    term + timer
    for term, timer in zip(TERM_TILES, TIMER_TILES, strict=True)
)

LOGO_TILES = tuple(
    word + cube
    for word, cube in zip(WORD_TILES, CUBE_TILES, strict=True)
)

WORD_WIDTH = len(WORD_TILES[0])
LOGO_WIDTH = len(LOGO_TILES[0])

# Diagonal 256-color ramps, one per time of day
NIGHT_RAMP = (27, 63, 99, 135, 171, 207, 201)
MORNING_RAMP = (199, 205, 211, 217, 195, 123, 51)
NOON_RAMP = (231, 230, 229, 228, 227, 226, 220, 214)
AFTERNOON_RAMP = (226, 220, 214, 208, 204, 199, 165, 129)
EVENING_RAMP = (51, 45, 39, 69, 99, 135, 171, 201)

MORNING_START = 6
NOON_START = 11
AFTERNOON_START = 14
EVENING_START = 18
NIGHT_START = 22

Lab = tuple[float, float, float]
Rgb = tuple[int, int, int]

# Position of the cube cursor in the grid, read from its tiles
CUBE_TOP = next(
    index for index, row in enumerate(CUBE_TILES) if TILE_STICKER in row
)
CUBE_LEFT = WORD_WIDTH + CUBE_TILES[CUBE_TOP].index(TILE_STICKER)
STICKER_SIZE = 2
STICKER_PITCH = 3

# Lightness of the three sticker rows of the cube, lit from above
STICKER_LIGHTNESS = (.034, 0, -.0408)

# The shadow is dark and half as saturated as the tile casting it
SHADOW_LIGHTNESS = .34
SHADOW_CHROMA = .5

VERSION_POSITION = 1
VERSION_LIGHTNESS = -.04
VERSION_CHROMA = 1.4

MODE_POSITION = .55
MODE_LIGHTNESS = -.02
MODE_CHROMA = 1.5
# The background of the terminal is unknown: the mode is written in black
MODE_COLOR = Color.from_rgb(0, 0, 0)

RULE = '═'
RULE_LIGHTNESS = -.18

UPPER_HALF = '▀'
LOWER_HALF = '▄'

GAMUT_TOLERANCE = 1e-4
GAMUT_STEP = .05

SRGB_LINEAR_LIMIT = .04045
LINEAR_SRGB_LIMIT = .0031308


def palette_for_hour(hour: int) -> tuple[int, ...]:
    """
    Select the color ramp matching an hour of the day.

    Args:
        hour: Hour of the day (0-23).

    Returns:
        The 256-color ramp of the corresponding time of day.

    """
    if MORNING_START <= hour < NOON_START:
        return MORNING_RAMP
    if NOON_START <= hour < AFTERNOON_START:
        return NOON_RAMP
    if AFTERNOON_START <= hour < EVENING_START:
        return AFTERNOON_RAMP
    if EVENING_START <= hour < NIGHT_START:
        return EVENING_RAMP
    return NIGHT_RAMP


def logo_tiles(width: int) -> tuple[str, ...] | None:
    """
    Select the tile grid fitting a terminal width.

    Args:
        width: Width of the terminal in columns.

    Returns:
        The whole logo, the word without its cube cursor on a narrower
        terminal, or None when even the word does not fit.

    """
    if width >= LOGO_WIDTH:
        return LOGO_TILES
    if width >= WORD_WIDTH:
        return WORD_TILES
    return None


def srgb_to_oklab(rgb: Rgb) -> Lab:
    """
    Convert an sRGB color to OKLab.

    Args:
        rgb: Red, green and blue components (0-255).

    Returns:
        The lightness and the two color axes of OKLab.

    """
    red, green, blue = (
        value / 12.92
        if value <= SRGB_LINEAR_LIMIT
        else ((value + .055) / 1.055) ** 2.4
        for value in (component / 255 for component in rgb)
    )
    long = math.cbrt(
        .4122214708 * red + .5363325363 * green + .0514459929 * blue,
    )
    medium = math.cbrt(
        .2119034982 * red + .6806995451 * green + .1073969566 * blue,
    )
    short = math.cbrt(
        .0883024619 * red + .2817188376 * green + .6299787005 * blue,
    )
    return (
        .2104542553 * long + .793617785 * medium - .0040720468 * short,
        1.9779984951 * long - 2.428592205 * medium + .4505937099 * short,
        .0259040371 * long + .7827717662 * medium - .808675766 * short,
    )


def oklab_to_srgb(lab: Lab) -> tuple[float, float, float]:
    """
    Convert an OKLab color to sRGB, without bringing it into gamut.

    Args:
        lab: Lightness and color axes of OKLab.

    Returns:
        Red, green and blue components, inside 0-1 when in gamut.

    """
    lightness, axis_a, axis_b = lab
    long = (lightness + .3963377774 * axis_a + .2158037573 * axis_b) ** 3
    medium = (lightness - .1055613458 * axis_a - .0638541728 * axis_b) ** 3
    short = (lightness - .0894841775 * axis_a - 1.291485548 * axis_b) ** 3
    red, green, blue = (
        12.92 * value
        if value <= LINEAR_SRGB_LIMIT
        else 1.055 * value ** (1 / 2.4) - .055
        for value in (
            4.0767416621 * long - 3.3077115913 * medium
            + .2309699292 * short,
            -1.2684380046 * long + 2.6097574011 * medium
            - .3413193965 * short,
            -.0041960863 * long - .7034186147 * medium
            + 1.707614701 * short,
        )
    )
    return red, green, blue


def oklab_to_rgb(lab: Lab) -> Rgb:
    """
    Convert an OKLab color to a displayable sRGB color.

    The chroma of a color outside the sRGB gamut is reduced step by
    step until it fits.

    Args:
        lab: Lightness and color axes of OKLab.

    Returns:
        Red, green and blue components (0-255).

    """
    lightness = min(1, max(0, lab[0]))
    scale = 1.0
    srgb = oklab_to_srgb((lightness, lab[1], lab[2]))
    while scale > 0 and not all(
            -GAMUT_TOLERANCE <= value <= 1 + GAMUT_TOLERANCE
            for value in srgb
    ):
        scale -= GAMUT_STEP
        srgb = oklab_to_srgb((lightness, lab[1] * scale, lab[2] * scale))
    red, green, blue = (
        math.floor(min(1, max(0, value)) * 255 + .5) for value in srgb
    )
    return red, green, blue


@cache
def ramp_stops(ramp: tuple[int, ...]) -> tuple[Lab, ...]:
    """
    Convert a 256-color ramp to its OKLab gradient stops.

    Args:
        ramp: 256-color indexes of the gradient.

    Returns:
        The OKLab color of each index.

    """
    return tuple(
        srgb_to_oklab(Color.from_ansi(index).get_truecolor())
        for index in ramp
    )


def ramp_color(
        ramp: tuple[int, ...], position: float,
        lightness: float = 0, chroma: float = 1,
) -> Lab:
    """
    Pick the color of a ramp at a position of its gradient.

    The stops are interpolated in OKLab, so that the passage between
    two distant hues stays clear instead of turning muddy.

    Args:
        ramp: 256-color indexes of the gradient.
        position: Position along the gradient, from 0 to 1.
        lightness: Lightness added to the color.
        chroma: Factor applied to the chroma of the color.

    Returns:
        The OKLab color at that position.

    """
    stops = ramp_stops(ramp)
    scaled = min(1, max(0, position)) * (len(stops) - 1)
    index = min(len(stops) - 2, int(scaled))
    fraction = scaled - index
    start = stops[index]
    end = stops[index + 1]
    return (
        start[0] + (end[0] - start[0]) * fraction + lightness,
        (start[1] + (end[1] - start[1]) * fraction) * chroma,
        (start[2] + (end[2] - start[2]) * fraction) * chroma,
    )


def tile_color(
        rows: tuple[str, ...], x: int, y: int, ramp: tuple[int, ...],
) -> Rgb | None:
    """
    Compute the color of one tile of a grid.

    The gradient runs along the diagonal of the grid. A sticker of the
    cube takes a single color, picked at its center.

    Args:
        rows: Rows of the tile grid.
        x: Column of the tile.
        y: Row of the tile.
        ramp: 256-color indexes of the gradient.

    Returns:
        Red, green and blue components (0-255), None for an empty tile.

    """
    tile = rows[y][x]
    if tile == TILE_EMPTY:
        return None

    span = len(rows[0]) - 1 + len(rows) - 1
    if tile == TILE_STICKER:
        column = (x - CUBE_LEFT) // STICKER_PITCH
        row = (y - CUBE_TOP) // STICKER_PITCH
        # x + y of the sticker center, half its size on each axis
        center = (
            CUBE_LEFT + CUBE_TOP + (column + row) * STICKER_PITCH
            + STICKER_SIZE
        )
        return oklab_to_rgb(
            ramp_color(ramp, center / span, STICKER_LIGHTNESS[row]),
        )

    lab = ramp_color(ramp, (x + y) / span)
    if tile == TILE_SHADOW:
        return oklab_to_rgb(
            (SHADOW_LIGHTNESS, lab[1] * SHADOW_CHROMA, lab[2] * SHADOW_CHROMA),
        )
    return oklab_to_rgb(lab)


def append_logo(
        banner: Text, rows: tuple[str, ...], ramp: tuple[int, ...],
) -> None:
    """
    Append the logo to a banner, two rows of tiles per line.

    Args:
        banner: Banner receiving the half-block lines.
        rows: Rows of the tile grid.
        ramp: 256-color indexes of the gradient.

    """
    for y in range(0, len(rows), 2):
        for x in range(len(rows[y])):
            top = tile_color(rows, x, y, ramp)
            bottom = tile_color(rows, x, y + 1, ramp)
            if top and bottom:
                banner.append(
                    UPPER_HALF,
                    Style(
                        color=Color.from_rgb(*top),
                        bgcolor=Color.from_rgb(*bottom),
                    ),
                )
            elif top:
                banner.append(UPPER_HALF, Style(color=Color.from_rgb(*top)))
            elif bottom:
                banner.append(
                    LOWER_HALF, Style(color=Color.from_rgb(*bottom)),
                )
            else:
                banner.append(' ')
        banner.append('\n')


def append_footer(
        banner: Text, width: int, ramp: tuple[int, ...], mode: str | None,
) -> None:
    """
    Append the rule to a banner, the version and the mode at its end.

    Args:
        banner: Banner receiving the footer line.
        width: Width of the logo in columns.
        ramp: 256-color indexes of the gradient.
        mode: Optional mode label displayed as a badge.

    """
    version = f'v{ COMMIT_HASH or __version__ }'
    badge = f' { mode.upper() } ' if mode else ''
    inset = len(version) + (len(badge) + 1 if badge else 0)

    for column in range(width - inset - 2):
        color = oklab_to_rgb(
            ramp_color(ramp, column / (width - 1), RULE_LIGHTNESS),
        )
        banner.append(RULE, Style(color=Color.from_rgb(*color)))

    version_color = oklab_to_rgb(
        ramp_color(
            ramp, VERSION_POSITION, VERSION_LIGHTNESS, VERSION_CHROMA,
        ),
    )
    banner.append(' ')
    banner.append(version, Style(color=Color.from_rgb(*version_color)))

    if badge:
        mode_color = oklab_to_rgb(
            ramp_color(ramp, MODE_POSITION, MODE_LIGHTNESS, MODE_CHROMA),
        )
        banner.append(' ')
        banner.append(
            badge,
            Style(color=MODE_COLOR, bgcolor=Color.from_rgb(*mode_color)),
        )


def get_commit_hash() -> str | None:
    """
    Read the short hash of the current commit for git installations.

    The git refs are read directly from the .git directory to avoid
    spawning an external process. Both loose and packed refs are
    supported.

    Returns:
        The short commit hash, or None if not installed from git.

    """
    head = GIT_DIR / 'HEAD'
    try:
        content = head.read_text().strip()
    except OSError:
        return None

    if not content.startswith('ref:'):
        return content[:SHORT_HASH_LENGTH] or None

    ref = content.removeprefix('ref:').strip()

    loose = GIT_DIR / ref
    try:
        return loose.read_text().strip()[:SHORT_HASH_LENGTH] or None
    except OSError:
        pass

    packed = GIT_DIR / 'packed-refs'
    try:
        lines = packed.read_text().splitlines()
    except OSError:
        return None

    for line in lines:
        if line.startswith(('#', '^')):
            continue
        commit, _, name = line.partition(' ')
        if name == ref:
            return commit[:SHORT_HASH_LENGTH] or None

    return None


COMMIT_HASH = get_commit_hash()


def get_banner(
        mode: str | None = None, hour: int | None = None,
        width: int = LOGO_WIDTH,
) -> Text | None:
    """
    Build the colorized splash screen banner.

    Args:
        mode: Optional mode label displayed next to the version.
        hour: Hour used to pick the palette (default: current local hour).
        width: Width of the terminal in columns.

    Returns:
        The banner, without its cube cursor when the terminal is too
        narrow for it, or None when even the word does not fit.

    """
    rows = logo_tiles(width)
    if rows is None:
        return None

    if hour is None:
        hour = datetime.now(UTC).astimezone().hour
    ramp = palette_for_hour(hour)

    banner = Text()
    append_logo(banner, rows, ramp)
    append_footer(banner, len(rows[0]), ramp, mode)
    return banner


def show_banner(mode: str | None = None, hour: int | None = None) -> None:
    """
    Display the splash screen banner on the console.

    Nothing is displayed on a terminal too narrow for the word.

    Args:
        mode: Optional mode label displayed next to the version.
        hour: Hour used to pick the palette (default: current local hour).

    """
    banner = get_banner(mode=mode, hour=hour, width=console.width)
    if banner is not None:
        console.print(banner)
