"""OpenGL renderer for animated cube visualization."""

import time
from operator import neg
from typing import TYPE_CHECKING
from typing import Final

from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_QUADS
from OpenGL.GL import GL_TEXTURE_2D
from OpenGL.GL import glBegin
from OpenGL.GL import glColor3fv
from OpenGL.GL import glDisable
from OpenGL.GL import glEnable
from OpenGL.GL import glEnd
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glNormal3fv
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glRotatef
from OpenGL.GL import glTexCoord2iv
from OpenGL.GL import glTranslatef
from OpenGL.GL import glVertex3fv

from term_timer.constants import Face
from term_timer.opengl.data import BLACK
from term_timer.opengl.data import center_colors_table
from term_timer.opengl.data import center_list
from term_timer.opengl.data import center_positions_table
from term_timer.opengl.data import color_list
from term_timer.opengl.data import corner_colors_table
from term_timer.opengl.data import corner_list
from term_timer.opengl.data import corner_orientation_axis_table
from term_timer.opengl.data import corner_permutations
from term_timer.opengl.data import corner_positions_table
from term_timer.opengl.data import edge_colors_table
from term_timer.opengl.data import edge_list
from term_timer.opengl.data import edge_orientation_axis_table
from term_timer.opengl.data import edge_permutations
from term_timer.opengl.data import edge_positions_table
from term_timer.opengl.data import hide_coords
from term_timer.opengl.data import indices
from term_timer.opengl.data import normals
from term_timer.opengl.data import rotation_axis
from term_timer.opengl.data import s
from term_timer.opengl.data import tex_map
from term_timer.opengl.data import vertices

if TYPE_CHECKING:
    from term_timer.opengl.cube import Cube
    from term_timer.opengl.window import Window


# Easing functions for smooth animations
def ease_out_cubic(t: float) -> float:
    """
    Ease-out cubic function for smooth deceleration.

    Starts fast, ends slow - feels natural and satisfying.
    t: normalized time from 0.0 to 1.0
    Returns: eased value from 0.0 to 1.0
    """
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t: float) -> float:
    """
    Ease-in-out cubic for smooth acceleration and deceleration.

    Starts slow, speeds up in middle, slows at end.
    t: normalized time from 0.0 to 1.0
    Returns: eased value from 0.0 to 1.0
    """
    if t < 0.5:  # noqa: PLR2004
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


# Pre-compute color index mapping for faster lookups
_CENTER_COLOR_INDEX: Final[dict[str, int]] = {
    center: idx for idx, center in enumerate(center_list)
}

# Gap factor for realistic piece separation (matches data.py)
_GAP_FACTOR: Final = 0.96

# Pre-compute face points for scale=1 with gap factor
_UNIT_CUBE_FACES: Final[list[list[tuple[float, float, float]]]] = [
    [
        (s[j][0] * _GAP_FACTOR, s[j][1] * _GAP_FACTOR, s[j][2] * _GAP_FACTOR)
        for j in indices[i]
    ]
    for i in range(6)
]

# Pre-cache texture coordinates for fast access
_TEX_COORDS: Final = (tex_map[0], tex_map[1], tex_map[2], tex_map[3])


def r_surface(
    points: (list[tuple[int, int, int]] | list[tuple[float, float, float]] |
             list[list[float]]),
    color: tuple[float, float, float] | None,
    normal: tuple[float, float, float] | None = None,
) -> None:
    if color is not None:
        glColor3fv(color)
        # Set normal once for the entire quad (flat shading)
        if normal is not None:
            glNormal3fv(normal)
        glBegin(GL_QUADS)
        # Unroll loop and use cached texture coords for better performance
        glTexCoord2iv(_TEX_COORDS[0])
        glVertex3fv(points[0])
        glTexCoord2iv(_TEX_COORDS[1])
        glVertex3fv(points[1])
        glTexCoord2iv(_TEX_COORDS[2])
        glVertex3fv(points[2])
        glTexCoord2iv(_TEX_COORDS[3])
        glVertex3fv(points[3])
        glEnd()


def r_cube(
    colors: list[tuple[float, float, float] | None],
    scale: float = 1,
) -> None:
    # Optimize by using pre-computed face points and inlining for scale=1
    if scale == 1:
        # Inline rendering for common case (scale=1) - reduces function calls
        for i in range(6):
            color = colors[i]
            face_color = color or BLACK
            points = _UNIT_CUBE_FACES[i]
            normal = normals[i]

            # Inlined r_surface for better performance
            glColor3fv(face_color)
            glNormal3fv(normal)
            glBegin(GL_QUADS)
            glTexCoord2iv(_TEX_COORDS[0])
            glVertex3fv(points[0])
            glTexCoord2iv(_TEX_COORDS[1])
            glVertex3fv(points[1])
            glTexCoord2iv(_TEX_COORDS[2])
            glVertex3fv(points[2])
            glTexCoord2iv(_TEX_COORDS[3])
            glVertex3fv(points[3])
            glEnd()
    else:
        # Scale vertices only once
        vertices_list = vertices(scale)
        for i, color in enumerate(colors):
            # Render all faces: colored stickers or black plastic interior
            face_color = color if color is not None else BLACK
            points_float: list[list[float]] = [
                vertices_list[j] for j in indices[i]
            ]
            r_surface(points_float, face_color, normals[i])


def get_orientation_param(
    piece: str,
    position: int,
    orientation: int,
) -> tuple[int, int, int, int]:
    if len(piece) == 2:
        rot_x, rot_y, rot_z = edge_orientation_axis_table[position]
        theta = 180 * orientation
    elif len(piece) == 3:
        rot_x, rot_y, rot_z = corner_orientation_axis_table[position]
        theta = -120 * orientation
    else:
        rot_x, rot_y, rot_z, theta = 0, 0, 0, 0
    return rot_x, rot_y, rot_z, theta


def render_piece(piece: str, position: int, orientation: int) -> None:
    # Use cached color index mapping for O(1) lookups instead of O(n)
    c: list[tuple[float, float, float]] = [
        color_list[_CENTER_COLOR_INDEX[e]] for e in piece
    ]
    colors: list[tuple[float, float, float] | None] = [None] * 6

    rot_x, rot_y, rot_z, theta = get_orientation_param(
        piece, position, orientation,
    )

    d_x: int
    d_y: int
    d_z: int

    if len(piece) == 1:
        d_x, d_y, d_z = center_positions_table[position]

        for i in center_colors_table[position]:
            colors[i] = c.pop(0)

    elif len(piece) == 2:
        d_x, d_y, d_z = edge_positions_table[position]

        for i in edge_colors_table[position]:
            colors[i] = c.pop(0)

    elif len(piece) == 3:
        d_x, d_y, d_z = corner_positions_table[position]

        for i in corner_colors_table[position]:
            colors[i] = c.pop(0)
    else:
        d_x, d_y, d_z = 0, 0, 0

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()

    glRotatef(theta, rot_x, rot_y, rot_z)
    glTranslatef(d_x, d_y, d_z)

    r_cube(colors)
    glPopMatrix()


def get_moving_pieces(
    cube: 'Cube',
    face: Face,
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int, int]]]:
    moving_pieces: list[tuple[str, int, int]] = []
    non_moving_pieces: list[tuple[str, int, int]] = []
    corner_p = cube.corner_permutation
    corner_o = cube.corners_orientations
    edge_p = cube.edge_permutation
    edge_o = cube.edges_orientations

    for i in range(6):
        if face == center_list[i]:
            moving_pieces.append((center_list[i], i, 0))
        else:
            non_moving_pieces.append((center_list[i], i, 0))

    for i in range(8):
        if corner_permutations[face][i] != i:
            moving_pieces.append((corner_list[corner_p[i]], i, corner_o[i]))
        else:
            non_moving_pieces.append((corner_list[corner_p[i]], i, corner_o[i]))
    for i in range(12):
        if edge_permutations[face][i] != i:
            moving_pieces.append((edge_list[edge_p[i]], i, edge_o[i]))
        else:
            non_moving_pieces.append((edge_list[edge_p[i]], i, edge_o[i]))
    return moving_pieces, non_moving_pieces


def get_rotation_param(face: Face,
                       power: int) -> tuple[tuple[int, int, int], int]:
    axis: tuple[int, int, int]
    axis = tuple(
        map(
            neg, rotation_axis[face],
        ),
    ) if power == 3 else rotation_axis[face]  # type: ignore[assignment]
    theta_max = 181 if power == 2 else 91

    return axis, theta_max


def render(cube: 'Cube') -> None:
    corner_p = cube.corner_permutation
    corner_o = cube.corners_orientations
    edge_p = cube.edge_permutation
    edge_o = cube.edges_orientations

    # Enable texture once for entire render
    glEnable(GL_TEXTURE_2D)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()

    rot_x, rot_y, rot_z = cube.get_euler_angles()

    glRotatef(rot_z, 0, 0, 1)
    glRotatef(rot_y, 0, 1, 0)
    glRotatef(rot_x, 1, 0, 0)

    for i in range(6):
        render_piece(center_list[i], i, 0)
    for i in range(12):
        render_piece(edge_list[edge_p[i]], i, edge_o[i])
    for i in range(8):
        render_piece(corner_list[corner_p[i]], i, corner_o[i])

    glPopMatrix()

    glDisable(GL_TEXTURE_2D)


def animate_move(window: 'Window', cube: 'Cube',  # noqa: PLR0914
                 face: Face, power: int) -> None:
    moving_pieces, non_moving_pieces = get_moving_pieces(cube, face)
    axis, theta_max = get_rotation_param(face, power)

    hiding_points = hide_coords[face]

    # Animation parameters (time-based for consistent speed)
    animation_duration = 0.075  # 75ms animation (balanced speed)
    target_angle = theta_max - 1  # Target rotation angle
    start_time = time.time()

    while True:
        # Calculate elapsed time
        elapsed = time.time() - start_time
        t = min(elapsed / animation_duration, 1.0)  # Clamp to [0, 1]

        # Apply ease-out cubic easing for smooth deceleration
        eased_t = ease_out_cubic(t)

        # Calculate current angle based on eased progress
        theta = eased_t * target_angle

        window.prepare()

        # Enable texture once for entire frame
        glEnable(GL_TEXTURE_2D)

        glMatrixMode(GL_MODELVIEW)

        glPushMatrix()

        rot_x, rot_y, rot_z = cube.get_euler_angles()
        glRotatef(rot_z, 0, 0, 1)
        glRotatef(rot_y, 0, 1, 0)
        glRotatef(rot_x, 1, 0, 0)

        glRotatef(theta, axis[0], axis[1], axis[2])
        for i in range(9):
            piece, pos, ori = moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, BLACK)
        glPopMatrix()

        glPushMatrix()
        glRotatef(rot_z, 0, 0, 1)
        glRotatef(rot_y, 0, 1, 0)
        glRotatef(rot_x, 1, 0, 0)

        for i in range(17):
            piece, pos, ori = non_moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, BLACK)
        glPopMatrix()

        glDisable(GL_TEXTURE_2D)

        window.update()

        # Break when animation is complete
        if t >= 1.0:
            break


def animate_rotation(window: 'Window', cube: 'Cube',
                     axis: str, angle: int) -> None:
    # Animation parameters (time-based for consistent speed)
    animation_duration = 0.075  # 75ms animation (balanced speed)
    start_time = time.time()
    prev_eased_angle = 0.0

    while True:
        # Calculate elapsed time
        elapsed = time.time() - start_time
        t = min(elapsed / animation_duration, 1.0)  # Clamp to [0, 1]

        # Apply ease-out cubic easing
        eased_t = ease_out_cubic(t)

        # Calculate current angle based on eased progress
        current_eased_angle = eased_t * angle

        # Calculate delta from previous frame
        delta_angle = current_eased_angle - prev_eased_angle

        window.prepare()

        if axis == 'x':
            cube.rotate_x(delta_angle)
        elif axis == 'y':
            cube.rotate_y(delta_angle)
        elif axis == 'z':
            cube.rotate_z(delta_angle)

        render(cube)
        window.update()

        prev_eased_angle = current_eased_angle

        # Break when animation is complete
        if t >= 1.0:
            break
