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

from term_timer.gl.data import NOIR
from term_timer.gl.data import axe_rotation
from term_timer.gl.data import hide_coords
from term_timer.gl.data import indices
from term_timer.gl.data import liste_aretes
from term_timer.gl.data import liste_centres
from term_timer.gl.data import liste_coins
from term_timer.gl.data import liste_couleurs
from term_timer.gl.data import permutations_aretes
from term_timer.gl.data import permutations_coins
from term_timer.gl.data import s
from term_timer.gl.data import sommets
from term_timer.gl.data import table_axe_orientation_aretes
from term_timer.gl.data import table_axe_orientation_coins
from term_timer.gl.data import table_couleurs_aretes
from term_timer.gl.data import table_couleurs_centres
from term_timer.gl.data import table_couleurs_coins
from term_timer.gl.data import table_positions_aretes
from term_timer.gl.data import table_positions_centres
from term_timer.gl.data import table_positions_coins
from term_timer.gl.data import tex_map


def r_surface(points, couleur):
    glEnable(GL_TEXTURE_2D)
    if couleur is not None:
        glColor3fv(couleur)
        glBegin(GL_QUADS)
        for i in range(4):
            glTexCoord2iv(tex_map[i])
            glVertex3fv(points[i])
        glEnd()
    glDisable(GL_TEXTURE_2D)


def r_cube(couleurs, echelle=1):
    liste_sommets = s if echelle == 1 else sommets(float(echelle))

    for i in range(6):
        points = [liste_sommets[j] for j in indices[i]]
        r_surface(points, couleurs[i])


def get_orientation_param(piece, position, orientation):
    if len(piece) == 2:
        rot_x, rot_y, rot_z = table_axe_orientation_aretes[position]
        theta = 180 * orientation
    elif len(piece) == 3:
        rot_x, rot_y, rot_z = table_axe_orientation_coins[position]
        theta = -120 * orientation
    else:
        rot_x, rot_y, rot_z, theta = 0, 0, 0, 0
    return rot_x, rot_y, rot_z, theta


def render_piece(piece, position, orientation):
    c = [liste_couleurs[liste_centres.index(e)] for e in piece]
    couleurs = [None] * 6

    rot_x, rot_y, rot_z, theta = get_orientation_param(
        piece, position, orientation,
    )

    if len(piece) == 1:
        d_x, d_y, d_z = table_positions_centres[position]

        for i in table_couleurs_centres[position]:
            couleurs[i] = c.pop(0)

    elif len(piece) == 2:
        d_x, d_y, d_z = table_positions_aretes[position]

        for i in table_couleurs_aretes[position]:
            couleurs[i] = c.pop(0)

    elif len(piece) == 3:
        d_x, d_y, d_z = table_positions_coins[position]

        for i in table_couleurs_coins[position]:
            couleurs[i] = c.pop(0)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()

    glRotatef(theta, rot_x, rot_y, rot_z)
    glTranslatef(d_x, d_y, d_z)

    r_cube(couleurs)
    glPopMatrix()


def get_moving_pieces(cube, face):
    moving_pieces, non_moving_pieces = [], []
    corner_p = cube.corner_permutation
    corner_o = cube.corners_orientations
    edge_p = cube.edge_permutation
    edge_o = cube.edges_orientations

    for i in range(6):
        if face == liste_centres[i]:
            moving_pieces.append((liste_centres[i], i, 0))
        else:
            non_moving_pieces.append((liste_centres[i], i, 0))

    for i in range(8):
        if permutations_coins[face][i] != i:
            moving_pieces.append((liste_coins[corner_p[i]], i, corner_o[i]))
        else:
            non_moving_pieces.append((liste_coins[corner_p[i]], i, corner_o[i]))
    for i in range(12):
        if permutations_aretes[face][i] != i:
            moving_pieces.append((liste_aretes[edge_p[i]], i, edge_o[i]))
        else:
            non_moving_pieces.append((liste_aretes[edge_p[i]], i, edge_o[i]))
    return moving_pieces, non_moving_pieces


def get_rotation_param(face, power):
    axe = tuple(map(lambda x: -x, axe_rotation[face])) if power == 3 else axe_rotation[face]
    theta_max = 181 if power == 2 else 91
    return axe, theta_max


def render(cube):
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
        render_piece(liste_centres[i], i, 0)
    for i in range(12):
        render_piece(liste_aretes[edge_p[i]], i, edge_o[i])
    for i in range(8):
        render_piece(liste_coins[corner_p[i]], i, corner_o[i])

    glPopMatrix()


def animate_move(window, cube, face, power):
    moving_pieces, non_moving_pieces = get_moving_pieces(cube, face)
    axe, theta_max = get_rotation_param(face, power)

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

        glRotatef(theta, axe[0], axe[1], axe[2])
        for i in range(9):
            piece, pos, ori = moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, NOIR)
        glPopMatrix()

        glPushMatrix()
        glRotatef(rot_z, 0, 0, 1)
        glRotatef(rot_y, 0, 1, 0)
        glRotatef(rot_x, 1, 0, 0)

        for i in range(17):
            piece, pos, ori = non_moving_pieces[i]
            render_piece(piece, pos, ori)
        r_surface(hiding_points, NOIR)
        glPopMatrix()

        window.update()


def animate_rotation(window, cube, axis, angle):
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
