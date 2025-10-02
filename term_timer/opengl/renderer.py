from operator import neg
from typing import TYPE_CHECKING

from OpenGL.GL import GL_MODELVIEW
from OpenGL.GL import GL_QUADS
from OpenGL.GL import GL_TEXTURE_2D
from OpenGL.GL import glBegin
from OpenGL.GL import glColor3fv
from OpenGL.GL import glDisable
from OpenGL.GL import glEnable
from OpenGL.GL import glEnd
from OpenGL.GL import glMatrixMode
from OpenGL.GL import glPopMatrix
from OpenGL.GL import glPushMatrix
from OpenGL.GL import glRotatef
from OpenGL.GL import glTexCoord2iv
from OpenGL.GL import glTranslatef
from OpenGL.GL import glVertex3fv

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
from term_timer.opengl.data import rotation_axis
from term_timer.opengl.data import s
from term_timer.opengl.data import tex_map
from term_timer.opengl.data import vertices

if TYPE_CHECKING:
    from term_timer.opengl.cube import Cube
    from term_timer.opengl.window import Window


def r_surface(
    points: list[tuple[int, int, int]] | list[list[float]],
    color: tuple[float, float, float] | None,
) -> None:
    glEnable(GL_TEXTURE_2D)
    if color is not None:
        glColor3fv(color)
        glBegin(GL_QUADS)
        for i in range(4):
            glTexCoord2iv(tex_map[i])
            glVertex3fv(points[i])
        glEnd()
    glDisable(GL_TEXTURE_2D)


def r_cube(
    colors: list[tuple[float, float, float] | None],
    scale: float = 1,
) -> None:
    if scale == 1:
        for i in range(6):
            points: list[tuple[int, int, int]] = [s[j] for j in indices[i]]
            r_surface(points, colors[i])
    else:
        vertices_list = vertices(scale)
        for i in range(6):
            points_float: list[list[float]] = [
                vertices_list[j] for j in indices[i]
            ]
            r_surface(points_float, colors[i])


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
    c: list[tuple[float, float, float]] = [
        color_list[center_list.index(e)] for e in piece
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
    face: str,
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


def get_rotation_param(face: str,
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


def animate_move(window: 'Window', cube: 'Cube', face: str, power: int) -> None:
    moving_pieces, non_moving_pieces = get_moving_pieces(cube, face)
    axis, theta_max = get_rotation_param(face, power)

    hiding_points = hide_coords[face]
    speed = 6

    for theta in range(1, theta_max, speed):
        window.prepare()

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

        window.update()


def animate_rotation(window: 'Window', cube: 'Cube',
                     axis: str, angle: int) -> None:
    speed = 6
    steps = range(1, angle + 1, speed)

    original_matrix = [row[:] for row in cube.rotation_matrix]

    for step in steps:
        window.prepare()

        current_angle = min(step, angle)

        if axis == 'x':
            cube.rotate_x(current_angle)
        elif axis == 'y':
            cube.rotate_y(current_angle)
        elif axis == 'z':
            cube.rotate_z(current_angle)

        render(cube)
        window.update()

        cube.rotation_matrix = [row[:] for row in original_matrix]

    if axis == 'x':
        cube.rotate_x(angle)
    elif axis == 'y':
        cube.rotate_y(angle)
    elif axis == 'z':
        cube.rotate_z(angle)
