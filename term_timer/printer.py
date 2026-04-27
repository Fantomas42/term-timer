"""Cube visualization and scramble display utilities."""
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.vcube import VCube

from term_timer.config import CUBE_EFFECT
from term_timer.config import CUBE_LINEAR
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import CUBE_PALETTE
from term_timer.config import CUBE_STYLE
from term_timer.formatter import format_float
from term_timer.interface.console import console


def print_cube_scrambled(
        cube: VCube,
        orientation: CubeOrientation,
        scramble: Algorithm,
) -> None:
    """
    Display a cube visualization with scramble information.

    Prints the cube state in the specified orientation and
    appends the scramble percentage indicating how much of the cube has been
    affected by the scramble algorithm. The scramble percentage is displayed
    with a 'scrambled' style using the Rich console library.

    Args:
        cube: The VCube object containing the current cube state in facelet
            string format.
        orientation: Two-character string specifying the cube orientation
            for display (e.g., 'UF' for Up-Front).
        scramble: Algorithm object representing the scramble sequence applied
            to the cube.

    """
    if orientation == 'auto':
        orientation = CUBE_ORIENTATION

    cube_display = cube.display(
        layout='linear' if CUBE_LINEAR else '',
        orientation=orientation,
        palette=CUBE_PALETTE,
        effect=CUBE_EFFECT,
        style=CUBE_STYLE,
    )

    cube_display = cube_display.rstrip('\n')

    print(cube_display, end='')  # noqa: T201

    impacts = scramble.impacts(cube.size)

    scrambled_percent = format_float(
        impacts.facelets_scrambled_percent * 100,
    )
    infos = f' [scrambled]{ scrambled_percent }%[/scrambled]'

    if (
            impacts.cubies_patterns
            and 'EO_COMPLETE' in impacts.cubies_patterns.orientation
    ):
        infos += ' [eo]EO[/eo]'

    console.print(infos)


def print_cube_trainer(
        cube: VCube,
        orientation: CubeOrientation,
        mode: str,
) -> None:
    """
    Display a cube visualization with specific training mode.

    Prints the cube state in the specified orientation and mode.

    Args:
        cube: The VCube object containing the current cube state in facelet
            string format.
        orientation: Two-character string specifying the cube orientation
            for display (e.g., 'UF' for Up-Front).
        mode: The training mode used (e.g., 'F2L', 'OLL').

    """
    print(  # noqa: T201
        cube.display(
            mode=mode,
            orientation=orientation,
            palette=CUBE_PALETTE,
            effect=CUBE_EFFECT,
            style=CUBE_STYLE,
        ),
        end='',
    )
